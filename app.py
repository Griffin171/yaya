import os
from flask import Flask, request, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env (para uso local)
load_dotenv()

# --- Configuração do Flask ---
# Usar instance_relative_config=True para que os caminhos relativos de configuração
# (como o do banco de dados SQLite para desenvolvimento local) sejam relativos à pasta 'instance'.
app = Flask(__name__, instance_relative_config=True)

# Configuração da URL do banco de dados
# O Render (e outras plataformas de hospedagem) fornecerá a URL do PostgreSQL
# através de uma variável de ambiente chamada 'DATABASE_URL'.
DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    # Se a URL começar com 'postgres://' (formato comum em algumas plataformas como Render/Heroku),
    # precisamos mudar para 'postgresql+psycopg2://' para que o SQLAlchemy a entenda corretamente.
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    # Fallback para SQLite para desenvolvimento local no seu computador.
    # Isso permite que você continue testando e desenvolvendo sem precisar de um PostgreSQL local.
    # Dados salvos aqui NÃO irão automaticamente para o site online.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuração da pasta de uploads de imagens
# As imagens serão salvas em 'static/uploads' dentro do seu projeto.
# Em produção no Render, essas imagens são salvas no sistema de arquivos do servidor,
# mas são voláteis se o servidor for reiniciado ou recriado.
# Para persistência de arquivos em produção a longo prazo, serviços como S3 (AWS) são usados.
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Cria a pasta 'static/uploads' se ela não existir

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limite de 16MB para upload

# Extensões de arquivo permitidas para upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Chave secreta para segurança da sessão do Flask.
# Em produção, esta chave DEVE ser carregada de variáveis de ambiente (Render).
# Em desenvolvimento local, ela pode vir do seu .env.
# É crucial que ela seja uma string longa e aleatória.
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura_e_longa_para_desenvolvimento_local_mude_em_producao')

# --- Modelo do Banco de Dados ---
# Define a estrutura da tabela 'image' no seu banco de dados (PostgreSQL ou SQLite)
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    filepath = db.Column(db.String(200), nullable=False) # Caminho relativo para o HTML
    title = db.Column(db.String(100), nullable=True)     # Campo para título da imagem
    description = db.Column(db.Text, nullable=True)      # Campo para descrição da imagem
    upload_date = db.Column(db.DateTime, default=datetime.utcnow) # Data e hora do upload

    def __repr__(self):
        # Representação amigável do objeto Image para depuração
        return f'<Image {self.filename}>'

# --- Funções Auxiliares ---
# Verifica se a extensão do arquivo é permitida
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Rotas do Flask ---

@app.route('/')
def index():
    """
    Renderiza a página principal (index.html) com o formulário de upload
    e exibe todas as imagens salvas no banco de dados, ordenadas pela data de upload.
    """
    try:
        # Consulta todas as imagens no banco de dados, ordenadas da mais recente para a mais antiga
        images = Image.query.order_by(Image.upload_date.desc()).all()
    except Exception as e:
        # Em caso de erro com o banco de dados (por exemplo, tabelas não criadas ou conexão),
        # imprime o erro e tenta renderizar a página sem imagens.
        print(f"Erro ao buscar imagens do banco de dados: {e}")
        images = [] # Lista vazia para evitar quebra na renderização do template

    # Passa as imagens (ou lista vazia em caso de erro) para o template HTML
    return render_template('index.html', images=images)

@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Lida com o upload de arquivos de imagem.
    Recebe o arquivo, título e descrição do formulário, salva a imagem
    na pasta de uploads e registra as informações no banco de dados.
    """
    # Verifica se um arquivo de imagem foi enviado no request
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo de imagem enviado'}), 400

    file = request.files['image']
    # Obtém o título e a descrição do formulário. Se não existirem, usa string vazia.
    title = request.form.get('title', '')
    description = request.form.get('description', '')

    # Verifica se um arquivo foi realmente selecionado (nome de arquivo não vazio)
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'}), 400

    # Processa o arquivo se for válido (permitido pela extensão)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename) # Garante um nome de arquivo seguro
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Caminho completo para salvar o arquivo
        file.save(full_path) # Salva o arquivo no sistema de arquivos do servidor

        # Caminho relativo que será salvo no DB e usado no HTML (ex: static/uploads/minha_imagem.jpg)
        # O .replace('\\', '/') é para garantir que o caminho use barras frontais,
        # que funcionam melhor em ambientes web (Linux no Render e HTML).
        relative_filepath = os.path.join('static', 'uploads', filename).replace('\\', '/')

        try:
            # Cria uma nova entrada no banco de dados para a imagem
            new_image = Image(filename=filename, filepath=relative_filepath, title=title, description=description)
            db.session.add(new_image) # Adiciona a nova imagem à sessão do DB
            db.session.commit()       # Confirma as mudanças no DB (salva no PostgreSQL/SQLite)

            # Retorna uma resposta JSON para o frontend (útil para feedback ao usuário)
            image_url = url_for('static', filename=os.path.join('uploads', filename))
            return jsonify({
                'success': True,
                'message': 'Upload realizado com sucesso!',
                'image_url': image_url,
                'filename': filename,
                'title': title,
                'description': description
            }), 200
        except Exception as e:
            # Em caso de erro ao salvar no banco de dados, imprime o erro
            print(f"Erro ao salvar imagem no banco de dados: {e}")
            # E retorna um erro para o frontend
            return jsonify({'success': False, 'message': f'Erro ao salvar dados da imagem: {e}'}), 500
    else:
        # Retorna erro se o tipo de arquivo não for permitido
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido'}), 400

# --- Inicialização da Aplicação ---
# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    with app.app_context():
        # Cria as tabelas do banco de dados (no PostgreSQL no Render, ou SQLite localmente).
        db.create_all()
    app.run(debug=False) # Inicia o servidor Flask em modo de depuração (NÃO USE EM PRODUÇÃO!)
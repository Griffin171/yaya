import os
from flask import Flask, request, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename # Para nomes de arquivo seguros
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv # Para carregar variáveis de ambiente

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# --- Configuração do Flask ---
# Usar instance_relative_config=True para que os caminhos relativos de configuração
# (como o do banco de dados) sejam relativos à pasta 'instance'
app = Flask(__name__, instance_relative_config=True)

# Configurações do banco de dados SQLite
# O banco de dados será salvo no arquivo 'instance/database.db'
# Usamos os.path.join(app.instance_path, 'database.db') para garantir o caminho absoluto correto
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configuração da pasta de uploads
# A pasta 'uploads' ficará dentro de 'static', que é acessível pelo navegador
# app.root_path aponta para o diretório raiz do seu aplicativo Flask (C:\yaya, neste caso)
UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True) # Cria a pasta 'static/uploads' se ela não existir

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 *1024 

# Extensões de arquivo permitidas
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Chave secreta para segurança da sessão (importante para ambientes de produção)
# Use uma chave secreta real e aleatória em produção.
# Crie um arquivo .env na raiz do seu projeto (C:\yaya\.env) com:
# FLASK_SECRET_KEY='sua_chave_secreta_aqui_gerada_por_os.urandom(24)'
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura')

# --- Modelo do Banco de Dados ---
# Define a estrutura da tabela 'image' no seu banco de dados
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
    # Consulta todas as imagens no banco de dados, ordenadas da mais recente para a mais antiga
    images = Image.query.order_by(Image.upload_date.desc()).all()
    # Passa as imagens para o template HTML
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
    title = request.form.get('title', '')       # Obtém o título do formulário
    description = request.form.get('description', '') # Obtém a descrição do formulário

    # Verifica se um arquivo foi realmente selecionado
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'}), 400

    # Processa o arquivo se for válido
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename) # Garante um nome de arquivo seguro
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename) # Caminho completo para salvar
        file.save(full_path) # Salva o arquivo no sistema de arquivos

        # Caminho relativo que será salvo no DB e usado no HTML (ex: static/uploads/minha_imagem.jpg)
        relative_filepath = os.path.join('static', 'uploads', filename).replace('\\', '/')

        # Cria uma nova entrada no banco de dados para a imagem
        new_image = Image(filename=filename, filepath=relative_filepath, title=title, description=description)
        db.session.add(new_image) # Adiciona a nova imagem à sessão do DB
        db.session.commit()       # Confirma as mudanças no DB

        # Retorna uma resposta JSON para o frontend (útil para atualizações dinâmicas)
        image_url = url_for('static', filename=os.path.join('uploads', filename))
        return jsonify({
            'success': True,
            'message': 'Upload realizado com sucesso!',
            'image_url': image_url,
            'filename': filename,
            'title': title, # Inclui o título na resposta
            'description': description # Inclui a descrição na resposta
        }), 200
    else:
        # Retorna erro se o tipo de arquivo não for permitido
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido'}), 400

# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    with app.app_context():
        # Cria a pasta 'instance' se ela não existir. Isso é crucial para o database.db.
        # O app.instance_path já garante o caminho correto para a pasta de instância.
        # os.makedirs(app.instance_path, exist_ok=True) # Isso é boa prática, mas o Flask já tenta criar ao usar app.instance_path para o DB.
        db.create_all() # Cria as tabelas do banco de dados se elas ainda não existirem
    app.run(debug=True) # Inicia o servidor Flask em modo de depuração
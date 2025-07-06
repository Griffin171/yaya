import os
from flask import Flask, request, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv
from flask_migrate import Migrate # Certifique-se de que Flask-Migrate está importado

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
    # Dados salvos aqui NÃO irão automaticamente para o site em produção.
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'

# Desabilita o rastreamento de modificações do SQLAlchemy, pois isso não é necessário
# para a maioria das aplicações e pode consumir recursos.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa o SQLAlchemy com o aplicativo Flask
db = SQLAlchemy(app)
# Inicializa o Flask-Migrate para gerenciar as migrações do banco de dados
migrate = Migrate(app, db)

# --- CRIAÇÃO INICIAL DAS TABELAS (Executado quando o Gunicorn carrega o app) ---
# Este bloco GARANTE que as tabelas sejam criadas se elas ainda não existirem.
# É crucial para a primeira implantação no Render, já que 'flask db upgrade'
# não está finalizando a execução automaticamente no ambiente.
# --- FIM DO BLOCO ESSENCIAL PARA CRIAÇÃO DE TABELAS ---

# --- Configuração do Upload de Imagens ---
# Define o diretório onde as imagens serão salvas localmente.
# NOTA: No Render, esta pasta é efêmera e não persistirá entre deploys ou reinícios.
# Para persistência, o Cloudinary (ou similar) é essencial.
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Define os tipos de arquivos permitidos para upload
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Verifica se a extensão do arquivo é permitida
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Configuração do Cloudinary (para armazenamento persistente) ---
# O Cloudinary é usado se as variáveis de ambiente estiverem configuradas.
# Caso contrário, o upload será apenas local (não persistente no Render).
CLOUDINARY_CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
CLOUDINARY_API_KEY = os.getenv('CLOUDINARY_API_KEY')
CLOUDINARY_API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET
    )
    print("Cloudinary configurado com sucesso!")
else:
    print("Cloudinary não configurado. O upload de imagens será apenas local (não persistente no Render).")


# --- Definição do Modelo do Banco de Dados ---
# Representa a tabela 'image' no seu banco de dados
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False) # Nome do arquivo original
    filepath = db.Column(db.String(500), nullable=False) # Caminho para o arquivo (local ou URL do Cloudinary)
    public_id = db.Column(db.String(200), nullable=True) # ID público do Cloudinary (se usado)
    title = db.Column(db.String(100), nullable=True)     # Título da imagem
    description = db.Column(db.Text, nullable=True)      # Descrição da imagem
    upload_date = db.Column(db.DateTime, default=datetime.utcnow) # Data de upload

    # Representação para depuração
    def __repr__(self):
        return f"Image('{self.filename}', '{self.title}', '{self.upload_date}')"


# --- Rotas da Aplicação Flask ---

# Rota principal que renderiza a página HTML
@app.route('/')
def index():
    return render_template('index.html')

# Rota para fazer upload de imagens
@app.route('/upload', methods=['POST'])
def upload_image():
    # Verifica se um arquivo foi enviado na requisição
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo de imagem enviado'}), 400

    file = request.files['image']

    # Se o nome do arquivo estiver vazio, retorna erro
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nome do arquivo inválido'}), 400

    # Se o arquivo existir e for permitido (extensão)
    if file and allowed_file(file.filename):
        try:
            # Obtém o título e a descrição do formulário (opcionais)
            title = request.form.get('title')
            description = request.form.get('description')

            filename = secure_filename(file.filename)
            file_path_for_db = None
            public_id = None

            # Tenta fazer upload para o Cloudinary primeiro
            if CLOUDINARY_CLOUD_NAME and CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET:
                try:
                    upload_result = cloudinary.uploader.upload(file)
                    file_path_for_db = upload_result['secure_url']
                    public_id = upload_result['public_id']
                    print(f"Upload para Cloudinary bem-sucedido: {file_path_for_db}")
                except Exception as e:
                    print(f"Erro ao fazer upload para Cloudinary: {e}. Tentando upload local.")
                    # Fallback para upload local se Cloudinary falhar
                    local_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(local_filepath)
                    file_path_for_db = url_for('static', filename=os.path.join('uploads', filename))
            else:
                # Apenas upload local se Cloudinary não estiver configurado
                local_filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                file.save(local_filepath)
                file_path_for_db = url_for('static', filename=os.path.join('uploads', filename))


            # Cria um novo objeto Image para salvar no banco de dados
            new_image = Image(
                filename=filename,
                filepath=file_path_for_db,
                public_id=public_id,
                title=title,
                description=description
            )

            db.session.add(new_image) # Adiciona a nova imagem à sessão do DB
            db.session.commit()       # Confirma as mudanças no DB (salva no PostgreSQL/SQLite)

            # Retorna uma resposta JSON para o frontend (útil para feedback ao usuário)
            return jsonify({
                'success': True,
                'message': 'Upload realizado com sucesso!',
                'image_url': file_path_for_db, # Retorna a URL do Cloudinary ou local
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

# Rota para obter todas as imagens cadastradas (API)
@app.route('/api/images', methods=['GET'])
def get_images():
    try:
        images = Image.query.order_by(Image.upload_date.desc()).all()
        # Converte os objetos Image em uma lista de dicionários para JSON
        images_data = []
        for image in images:
            images_data.append({
                'id': image.id,
                'filename': image.filename,
                'filepath': image.filepath,
                'public_id': image.public_id,
                'title': image.title,
                'description': image.description,
                'upload_date': image.upload_date.strftime('%Y-%m-%d %H:%M:%S') # Formata a data
            })
        return jsonify(images_data), 200
    except Exception as e:
        print(f"Erro ao buscar imagens para API: {e}")
        return jsonify({'success': False, 'message': f'Erro ao buscar imagens: {e}'}), 500

# Rota para deletar uma imagem
@app.route('/delete_image/<int:image_id>', methods=['DELETE'])
def delete_image(image_id):
    try:
        image = Image.query.get(image_id)
        if not image:
            return jsonify({'success': False, 'message': 'Imagem não encontrada'}), 404

        # Se a imagem foi salva no Cloudinary, exclua-a de lá também
        if image.public_id and CLOUDINARY_CLOUD_NAME:
            try:
                import cloudinary.uploader
                cloudinary.uploader.destroy(image.public_id)
                print(f"Imagem {image.public_id} deletada do Cloudinary.")
            except Exception as e:
                print(f"Erro ao deletar imagem do Cloudinary ({image.public_id}): {e}")
                # Não retorna erro fatal, pois a imagem local/registro DB ainda pode ser deletado

        # Deleta o registro do banco de dados
        db.session.delete(image)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Imagem deletada com sucesso'}), 200

    except Exception as e:
        print(f"Erro ao deletar imagem: {e}")
        return jsonify({'success': False, 'message': f'Erro ao deletar imagem: {e}'}), 500


# --- Inicialização da Aplicação (APENAS PARA USO LOCAL/DESENVOLVIMENTO) ---
# Este bloco só é executado se você rodar o arquivo diretamente (python app.py).
# Quando implantado com Gunicorn, este bloco é ignorado.
if __name__ == '__main__':
    app.run(debug=False)
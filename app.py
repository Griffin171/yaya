import os
from flask import Flask, request, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# --- Importar Cloudinary e Flask-Migrate ---
import cloudinary
import cloudinary.uploader
import cloudinary.api
from flask_migrate import Migrate # Adicione esta linha

# Carregar variáveis de ambiente do arquivo .env (para uso local)
load_dotenv()

# --- Configuração do Flask ---
app = Flask(__name__, instance_relative_config=True)

# Configuração do banco de dados
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- Configuração do Flask-Migrate ---
# É crucial que 'db' seja definido antes desta linha
migrate = Migrate(app, db) # Inicializa o Flask-Migrate

# --- Configuração do Cloudinary (usando variáveis de ambiente) ---
cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura_e_longa_para_desenvolvimento_local_mude_em_producao')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# --- Modelo do Banco de Dados ---
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    # filepath agora guarda a URL COMPLETA do Cloudinary
    filepath = db.Column(db.String(300), nullable=False) # Aumentei o tamanho para a URL completa do Cloudinary
    public_id = db.Column(db.String(100), nullable=False, unique=True) # ID público do Cloudinary para exclusão
    title = db.Column(db.String(100), nullable=True)
    description = db.Column(db.Text, nullable=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Image {self.filename}>'

# --- Funções Auxiliares ---
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Rotas do Flask ---

@app.route('/')
def index():
    """
    Renderiza a página principal (index.html).
    As imagens são carregadas via JavaScript.
    """
    return render_template('index.html')


@app.route('/api/images')
def get_all_images():
    """
    Retorna todas as imagens cadastradas no banco de dados em formato JSON,
    com as URLs do Cloudinary.
    """
    try:
        images = Image.query.order_by(Image.upload_date.desc()).all()
        images_data = []
        for image in images:
            images_data.append({
                'id': image.id,
                'filename': image.filename,
                'filepath': image.filepath, # Já é a URL do Cloudinary
                'public_id': image.public_id, # Retorna o public_id para o JS, se precisar
                'title': image.title,
                'description': image.description,
                'upload_date': image.upload_date.isoformat()
            })
        return jsonify(images_data), 200
    except Exception as e:
        print(f"Erro ao buscar imagens para API: {e}")
        return jsonify({'error': 'Erro ao carregar imagens.'}), 500


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo de imagem enviado'}), 400

    file = request.files['image']
    title = request.form.get('title', '')
    description = request.form.get('description', '')

    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado'}), 400

    if file and allowed_file(file.filename):
        try:
            # --- UPLOAD PARA O CLOUDINARY ---
            # O upload_stream aceita um objeto de arquivo.
            # O folder pode ser útil para organizar suas imagens no Cloudinary.
            # `resource_type='image'` é redundante para imagens, mas garante o tipo.
            upload_result = cloudinary.uploader.upload(file, folder="galeria-yaya")
            
            image_url = upload_result['secure_url'] # URL HTTPS da imagem no Cloudinary
            public_id = upload_result['public_id'] # ID único para referenciar a imagem no Cloudinary

            # --- SALVAR DADOS NO BANCO DE DADOS ---
            new_image = Image(
                filename=secure_filename(file.filename), # Use secure_filename para o nome original
                filepath=image_url,
                public_id=public_id,
                title=title,
                description=description
            )
            db.session.add(new_image)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Upload realizado com sucesso!',
                'image_url': image_url,
                'filename': secure_filename(file.filename),
                'title': title,
                'description': description
            }), 200
        except cloudinary.exceptions.Error as e:
            print(f"Erro no upload para Cloudinary: {e}")
            return jsonify({'success': False, 'message': f'Erro ao fazer upload da imagem: {e}'}), 500
        except Exception as e:
            print(f"Erro ao salvar imagem no banco de dados: {e}")
            return jsonify({'success': False, 'message': f'Erro interno do servidor: {e}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido'}), 400


@app.route('/delete/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    try:
        image_to_delete = db.session.get(Image, image_id)

        if not image_to_delete:
            return jsonify({'success': False, 'message': 'Desenho não encontrado.'}), 404

        # --- EXCLUIR DO CLOUDINARY ---
        # Usa o public_id salvo para deletar a imagem do Cloudinary
        cloudinary.uploader.destroy(image_to_delete.public_id)
        print(f"Imagem {image_to_delete.public_id} removida do Cloudinary.")

        # --- EXCLUIR DO BANCO DE DADOS ---
        db.session.delete(image_to_delete)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Desenho excluído com sucesso!'}), 200

    except cloudinary.exceptions.Error as e:
        print(f"Erro ao excluir imagem do Cloudinary: {e}")
        return jsonify({'success': False, 'message': f'Erro ao excluir imagem do Cloudinary: {e}'}), 500
    except Exception as e:
        print(f"Erro ao excluir desenho com ID {image_id}: {e}")
        return jsonify({'success': False, 'message': 'Erro ao excluir desenho.'}), 500


# --- Inicialização da Aplicação ---
# Com Flask-Migrate, você NÃO chama db.create_all() aqui para a produção.
# As migrações se encarregam da criação e atualização do esquema do DB.
if __name__ == '__main__':
    app.run(debug=True) # Mude para debug=False em produção!
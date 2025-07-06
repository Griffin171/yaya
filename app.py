import os
from flask import Flask, request, redirect, url_for, render_template, jsonify
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env (para uso local)
load_dotenv()

# --- Configuração do Flask ---
app = Flask(__name__, instance_relative_config=True)

DATABASE_URL = os.getenv('DATABASE_URL')

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'database.db')

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'sua_chave_secreta_padrao_muito_segura_e_longa_para_desenvolvimento_local_mude_em_producao')

# --- Modelo do Banco de Dados ---
class Image(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(100), nullable=False)
    filepath = db.Column(db.String(200), nullable=False) # Caminho relativo para o HTML
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
    As imagens agora serão carregadas via JavaScript.
    """
    return render_template('index.html')


@app.route('/api/images') # NOVA ROTA para o JavaScript buscar as imagens
def get_all_images():
    """
    Retorna todas as imagens cadastradas no banco de dados em formato JSON.
    Esta rota será usada pelo JavaScript para popular a galeria.
    """
    try:
        images = Image.query.order_by(Image.upload_date.desc()).all()
        # Converte a lista de objetos Image em uma lista de dicionários
        # com URLs completas para as imagens.
        images_data = []
        for image in images:
            # url_for('static', filename='uploads/' + image.filename) gera a URL correta
            image_url = url_for('static', filename=f'uploads/{image.filename}')
            images_data.append({
                'id': image.id,
                'filename': image.filename,
                'filepath': image_url, # Usar a URL gerada pelo Flask
                'title': image.title,
                'description': image.description,
                'upload_date': image.upload_date.isoformat() # Formato ISO para fácil parse no JS
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
        filename = secure_filename(file.filename)
        full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(full_path)

        # Usar o url_for para filepath também, garantindo que seja uma URL pública
        # A URL pública é o que o navegador realmente vai usar.
        relative_filepath = url_for('static', filename=f'uploads/{filename}')


        try:
            new_image = Image(filename=filename, filepath=relative_filepath, title=title, description=description)
            db.session.add(new_image)
            db.session.commit()

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
            print(f"Erro ao salvar imagem no banco de dados: {e}")
            return jsonify({'success': False, 'message': f'Erro ao salvar dados da imagem: {e}'}), 500
    else:
        return jsonify({'success': False, 'message': 'Tipo de arquivo não permitido'}), 400

@app.route('/delete/<int:image_id>', methods=['POST'])
def delete_image(image_id):
    try:
        image_to_delete = db.session.get(Image, image_id) # Usar db.session.get para buscar por PK

        if not image_to_delete:
            return jsonify({'success': False, 'message': 'Desenho não encontrado.'}), 404

        # O filepath no DB já é uma URL. Para remover, precisamos converter de volta para um caminho de sistema de arquivos.
        # Isto é um pouco mais complexo se a imagem não estiver no diretório 'static/uploads'.
        # Assumindo que a URL é tipo /static/uploads/nome_arquivo.jpg
        relative_path_from_static = image_to_delete.filepath.replace(url_for('static', filename=''), '')
        file_path = os.path.join(app.root_path, 'static', relative_path_from_static)

        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Arquivo {file_path} removido do sistema de arquivos.")
        else:
            print(f"Aviso: Arquivo {file_path} não encontrado no disco para exclusão (ou não é um caminho local).")


        db.session.delete(image_to_delete)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Desenho excluído com sucesso!'}), 200

    except Exception as e:
        print(f"Erro ao excluir desenho com ID {image_id}: {e}")
        return jsonify({'success': False, 'message': 'Erro ao excluir desenho.'}), 500


# --- Inicialização da Aplicação ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False)
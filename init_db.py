# init_db.py
import os
from app import app, db # Importa a instância 'app' e 'db' do seu app.py

def initialize_database():
    with app.app_context():
        print("Criando tabelas do banco de dados (se não existirem)...")
        db.create_all()
        print("Tabelas verificadas/criadas com sucesso!")

if __name__ == '__main__':
    initialize_database()
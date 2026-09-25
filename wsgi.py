from app import app, init_db_all

init_db_all()

if __name__ == '__main__':
    app.run()

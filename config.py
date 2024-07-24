import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'you-will-never-guess'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'app.db')
    # UPLOAD_FOLDER = os.path.join(os.getcwd(), 'uploads')
    UPLOAD_FOLDER = os.path.join(basedir, 'app/static/profile_pics')
    # MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # Maximum file size: 16MB

    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['Ayoaro85@gmail.com']
    POSTS_PER_PAGE = 10
    
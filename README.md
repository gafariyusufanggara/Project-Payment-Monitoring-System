1\. Bash console: 
git clone <url-github> hutang-app
mkdir -p \~/data-hutang
mkvirtualenv --python=/usr/bin/python3.13 hutang-env
pip install -r \~/hutang-app/requirements.txt


2\. Web tab > Add web app > Manual > Python 3.13
isi Source: /home/USERNAME/hutang-app
Virtualenv: /home/USERNAME/.virtualenvs/hutang-env


3\. Edit file WSGI /var/www/...\_wsgi.py jadi:


import os, sys

P='/home/USERNAME/hutang-app'

if P not in sys.path: sys.path.insert(0,P)

os.environ\['SECRET\_KEY']='isi-random-panjang'

os.environ\['APP\_PASSWORD']='password-tim'

os.environ\['DATA\_DIR']='/home/USERNAME/data-hutang'

os.environ\['DISABLE\_EXCEL\_AUTOMIGRATE']='1'

from app import app as application

from app import init\_db\_all

init\_db\_all()


4\. Reload web app, buka URL, login pakai APP\_PASSWORD, import Excel via UI.

Update berikutnya: git pull di \~/hutang-app lalu Reload.


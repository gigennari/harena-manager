# Django Server
## Running the Server

If it is your first time, we suggest you set up the environment, by first reading [PostgreSQL setup](setup-postgresql.md) and after the [Django setup](setup-django.md).

## Running the PostgreSQL DBMS

Inside the folder `/dbms`:
~~~
docker compose up
~~~

## Running a Virtual Environment for Django

Inside the root folder `/`:
~~~
source .venv/bin/activate
~~~

## Running the Django Server

Inside the folder `/mundorum`:

~~~
python3 manage.py runserver
~~~

## API Access

* api access: http://127.0.0.1:8000/
* admin address: http://127.0.0.1:8000/admin/
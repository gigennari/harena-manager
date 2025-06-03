# Django Server
## Setting up the Environment

These are the steps to set the environment for the first time.

## PostgreSQL DBMS Server

This server version works together with a PostgreSQL server. To set up and run the PostgreSQL, please visit the [PostgreSQL setup instructions](setup-postgresql.md).

## Configuring the `.env` variables

Copy the `.env-model` file to `.env` and update the variables, especially:
* `VITE_GOOGLE_CLIENT_ID`: This ID is used for authentication purposes when integrating Harena with Google with OAuth 2.0 for user login.
* `DJANGO_SECRET_KEY`: This secret key was transferred from the file settings.py.

## Creating a Virtual Environment for Django

Inside the root folder `/`:
~~~
python3 -m venv .venv
~~~

## Running a Virtual Environment for Django

Inside the root folder `/`:
~~~
source .venv/bin/activate
~~~

## Django Setup - Requirements Approach

Inside the root folder `/`:
~~~
pip install -r requirements.txt
~~~

## Building the Database

Inside the folder `/mundorum`:

~~~
python3 manage.py migrate
~~~

## Adding an admin user

Inside the folder `/mundorum`:

~~~
python3 manage.py createsuperuser
~~~

## Running the Server

To run the server, please visit [run.md](run.md).

## Handy Setup Stuff 
#### A hopefully helpful guide to environment configuration

Install postgresql
```bash
sudo apt install postgresql postgresql-contrib
```

Ensure the database is running (using `start` instead of `status` will start the process)
```bash
sudo service postgresql status
```

Add user named `discord` with corresponding db (superuser is convenient)
```bash
sudo -u postgres createuser --interactive
```
I guess get in the database with like 
```bash 
sudo -u postgres psql
``` 
and set a password with like `\password discord` (`\q` to exit)
Save those credentials to the config file.

Download data for spacy sentence parsing (used to improve markov chaining): 
```bash
pipenv python -m spacy download en_core_web_sm
```

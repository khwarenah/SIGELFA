import pyodbc
from werkzeug.security import generate_password_hash

conn_str = 'Driver={SQL Server};Server=DEMONBANE;Database=SIGELFA;UID=LoginArb1;PWD=ArbPassword123;'
conn = pyodbc.connect(conn_str, autocommit=True)
cursor = conn.cursor()

# Creamos solo al Super Admin para que pueda entrar al sistema web
user = 'admin'
pwd = 'adminpassword'
hash_pwd = generate_password_hash(pwd)
nombre = 'Administrador Sistema'
rol = 'Admin'

try:
    cursor.execute("""
        INSERT INTO Usuario_App (username, password_hash, nombre_real, rol)
        VALUES (?, ?, ?, ?)
    """, (user, hash_pwd, nombre, rol))
    print(f"[ÉXITO] Primer administrador '{user}' creado correctamente.")
except pyodbc.IntegrityError:
    print(f"[AVISO] El administrador '{user}' ya existe.")

conn.close()
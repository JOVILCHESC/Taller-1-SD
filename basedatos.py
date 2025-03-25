import sqlite3

# Conectar o crear la base de datos
conn = sqlite3.connect('mensajeria.db')
cursor = conn.cursor()

# Crear tabla de usuarios
cursor.execute('''
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
''')

# Crear tabla de contactos (relaciones)
cursor.execute('''
CREATE TABLE IF NOT EXISTS contactos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    contacto_id INTEGER NOT NULL,
    bloqueado INTEGER DEFAULT 0,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (contacto_id) REFERENCES usuarios(id)
)
''')

print("Base de datos y tablas creadas correctamente.")
conn.commit()
conn.close()

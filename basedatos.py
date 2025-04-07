import sqlite3
import os

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
# Crear tabla de archivos (actualizada para incluir el campo 'datos')
cursor.execute('''
CREATE TABLE IF NOT EXISTS archivos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    remitente_id INTEGER NOT NULL,
    destinatario_id INTEGER NOT NULL,
    nombre_archivo TEXT NOT NULL,
    ruta_archivo TEXT NOT NULL,
    tamano_archivo INTEGER NOT NULL, -- Tamaño del archivo en bytes
    datos BLOB, -- Datos binarios del archivo
    fecha_envio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado_transferencia TEXT DEFAULT 'pendiente', -- pendiente, en_progreso, completado, fallido
    FOREIGN KEY (remitente_id) REFERENCES usuarios(id),
    FOREIGN KEY (destinatario_id) REFERENCES usuarios(id)
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

# Crear tabla de sesiones de usuarios
cursor.execute('''
CREATE TABLE IF NOT EXISTS sesiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL,
    inicio_sesion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
)
''')

# Crear tabla para manejar transferencias en tiempo real
cursor.execute('''
CREATE TABLE IF NOT EXISTS transferencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    archivo_id INTEGER NOT NULL,
    progreso INTEGER DEFAULT 0, -- Porcentaje de transferencia (0-100)
    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado TEXT DEFAULT 'pendiente', -- pendiente, en_progreso, completado, fallido
    FOREIGN KEY (archivo_id) REFERENCES archivos(id)
)
''')

# Verificar las tablas existentes
print("Verificando tablas en la base de datos:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tablas = cursor.fetchall()
for tabla in tablas:
    print(f"  - {tabla[0]}")

print("\nEstructura de la tabla transferencias:")
try:
    cursor.execute("PRAGMA table_info(transferencias)")
    columnas = cursor.fetchall()
    tiene_columna_estado = False
    
    if columnas:
        for col in columnas:
            print(f"  - {col[1]} ({col[2]})")
            if col[1] == 'estado':
                tiene_columna_estado = True
    else:
        print("  ¡La tabla transferencias no tiene columnas!")
    
    # Si no tiene la columna 'estado', la agregamos
    if not tiene_columna_estado:
        print("\nAgregando columna 'estado' que falta en la tabla transferencias...")
        try:
            cursor.execute('''
            ALTER TABLE transferencias ADD COLUMN estado TEXT DEFAULT 'pendiente'
            ''')
            conn.commit()
            print("  Columna 'estado' agregada correctamente.")
        except sqlite3.Error as e:
            print(f"  Error al agregar la columna: {e}")
except sqlite3.Error as e:
    print(f"  Error al obtener estructura: {e}")

# Crear directorio para archivos temporales
upload_dir = "uploads"
if not os.path.exists(upload_dir):
    os.makedirs(upload_dir)
    print(f"\nDirectorio '{upload_dir}' creado para archivos temporales.")
else:
    print(f"\nDirectorio '{upload_dir}' ya existe.")

# Ejemplo comentado para evitar errores
'''
try:
    # Definir variables necesarias (ejemplo)
    remitente_id = 1
    destinatario_id = 2
    nombre_archivo = "archivo.txt"
    ruta_archivo = "ruta/del/archivo.txt"
    archivo_id = 1  # ID del archivo a recuperar

    # Validar que las variables necesarias estén definidas
    if not all([remitente_id, destinatario_id, nombre_archivo, ruta_archivo]):
        raise ValueError("Faltan variables necesarias para insertar datos en la tabla 'archivos'.")

    # Verificar si el archivo existe antes de intentar abrirlo
    if not os.path.exists(ruta_archivo):
        raise FileNotFoundError(f"El archivo '{ruta_archivo}' no existe.")

    with open(ruta_archivo, 'rb') as file:
        datos_binarios = file.read()

    cursor.execute("""
    INSERT INTO archivos (remitente_id, destinatario_id, nombre_archivo, ruta_archivo, tamano_archivo, datos)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (remitente_id, destinatario_id, nombre_archivo, ruta_archivo, len(datos_binarios), datos_binarios))

    # Recuperar archivo desde la base de datos
    cursor.execute('SELECT datos FROM archivos WHERE id = ?', (archivo_id,))
    archivo_binario = cursor.fetchone()
    if archivo_binario is None:
        raise ValueError(f"No se encontró un archivo con id {archivo_id}.")

    archivo_binario = archivo_binario[0]
    ruta_guardado = 'ruta_para_guardar_el_archivo'
    with open(ruta_guardado, 'wb') as file:
        file.write(archivo_binario)

    print(f"Archivo guardado exitosamente en '{ruta_guardado}'.")
'''

conn.commit()
conn.close()
print("Base de datos actualizada correctamente.")

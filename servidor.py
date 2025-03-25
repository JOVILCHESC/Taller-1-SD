import socket
import sqlite3
import time

# Configuración del socket UDP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('localhost', 12345))

print("Servidor UDP activo en puerto 12345...")

# Diccionario para almacenar las direcciones de usuarios conectados
# Formato: {username: dirección}
connected_users = {}

try:
    # Bucle principal del servidor
    while True:
        try:
            # Recibir mensaje de cliente
            message, address = server_socket.recvfrom(1024)
            request = message.decode().split('|')
            
            # REGISTRO DE USUARIO
            if request[0] == 'REGISTER':
                username, password = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                try:
                    # Intentar insertar nuevo usuario
                    cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", (username, password))
                    conn.commit()
                    server_socket.sendto("Registro exitoso".encode(), address)
                except sqlite3.IntegrityError:
                    # Error si el usuario ya existe (clave primaria duplicada)
                    server_socket.sendto("Usuario ya registrado".encode(), address)
                conn.close()

            # LOGIN DE USUARIO
            elif request[0] == 'LOGIN':
                username, password = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                # Verificar credenciales
                cursor.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
                if cursor.fetchone():
                    # Guardar dirección del usuario para enviar mensajes
                    connected_users[username] = address
                    
                    # Enviar respuesta de login exitoso
                    server_socket.sendto("Login exitoso".encode(), address)
                else:
                    server_socket.sendto("Credenciales incorrectas".encode(), address)
                conn.close()

            # AGREGAR CONTACTO
            elif request[0] == 'ADD_CONTACT':
                user, contact = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                # Obtener IDs de usuario y contacto
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (user,))
                user_id = cursor.fetchone()
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (contact,))
                contact_id = cursor.fetchone()
                
                if user_id and contact_id:
                    try:
                        # Insertar en la tabla de contactos
                        cursor.execute("INSERT INTO contactos (usuario_id, contacto_id) VALUES (?, ?)", 
                                    (user_id[0], contact_id[0]))
                        conn.commit()
                        # Enviar confirmación con el nombre del contacto añadido
                        server_socket.sendto(f"Contacto agregado: {contact}".encode(), address)
                    except sqlite3.IntegrityError:
                        # Error si el contacto ya existe (restricción UNIQUE)
                        server_socket.sendto("El contacto ya existe".encode(), address)
                else:
                    server_socket.sendto("Usuario no encontrado".encode(), address)
                conn.close()
            
            # BLOQUEAR CONTACTO
            elif request[0] == 'BLOCK_CONTACT':
                user, contact = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                # Obtener IDs
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (user,))
                user_id = cursor.fetchone()
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (contact,))
                contact_id = cursor.fetchone()
                
                if user_id and contact_id:
                    # Actualizar estado de bloqueo en la tabla de contactos
                    cursor.execute("""
                        UPDATE contactos 
                        SET bloqueado = 1 
                        WHERE usuario_id = ? AND contacto_id = ?
                    """, (user_id[0], contact_id[0]))
                    conn.commit()
                    server_socket.sendto(f"Contacto bloqueado: {contact}".encode(), address)
                else:
                    server_socket.sendto("Usuario no encontrado".encode(), address)
                conn.close()
                
            # DESBLOQUEAR CONTACTO
            elif request[0] == 'UNBLOCK_CONTACT':
                user, contact = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                # Obtener IDs
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (user,))
                user_id = cursor.fetchone()
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (contact,))
                contact_id = cursor.fetchone()
                
                if user_id and contact_id:
                    # Actualizar estado de bloqueo en la tabla de contactos
                    cursor.execute("""
                        UPDATE contactos 
                        SET bloqueado = 0 
                        WHERE usuario_id = ? AND contacto_id = ?
                    """, (user_id[0], contact_id[0]))
                    conn.commit()
                    server_socket.sendto(f"Contacto desbloqueado: {contact}".encode(), address)
                else:
                    server_socket.sendto("Usuario no encontrado".encode(), address)
                conn.close()
                
            # ELIMINAR CONTACTO
            elif request[0] == 'REMOVE_CONTACT':
                user, contact = request[1], request[2]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                # Obtener IDs
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (user,))
                user_id = cursor.fetchone()
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (contact,))
                contact_id = cursor.fetchone()
                
                if user_id and contact_id:
                    # Eliminar de la tabla de contactos
                    cursor.execute("""
                        DELETE FROM contactos 
                        WHERE usuario_id = ? AND contacto_id = ?
                    """, (user_id[0], contact_id[0]))
                    conn.commit()
                    server_socket.sendto(f"Contacto eliminado: {contact}".encode(), address)
                else:
                    server_socket.sendto("Usuario no encontrado".encode(), address)
                conn.close()
                
            # OBTENER LISTA DE CONTACTOS
            elif request[0] == 'GET_CONTACTS':
                username = request[1]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                
                # Obtener ID del usuario
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (username,))
                user_id_result = cursor.fetchone()
                
                if user_id_result:
                    user_id = user_id_result[0]
                    
                    # Obtener contactos y su estado de bloqueo
                    cursor.execute("""
                        SELECT u.username, IFNULL(c.bloqueado, 0) 
                        FROM contactos c
                        JOIN usuarios u ON c.contacto_id = u.id
                        WHERE c.usuario_id = ?
                    """, (user_id,))
                    
                    contacts = cursor.fetchall()
                    
                    if contacts:
                        # Formato de respuesta: CONTACTS|nombre1:estado1,nombre2:estado2,...
                        contacts_str = ",".join([f"{contact[0]}:{contact[1]}" for contact in contacts])
                        server_socket.sendto(f"CONTACTS|{contacts_str}".encode(), address)
                    else:
                        server_socket.sendto("CONTACTS|NONE".encode(), address)
                else:
                    server_socket.sendto("CONTACTS|NONE".encode(), address)
                    
                conn.close()

            # ENVIAR MENSAJE
            elif request[0] == 'SEND':
                from_user, to_user, msg = request[1], request[2], request[3]
                conn = sqlite3.connect('mensajeria.db')
                cursor = conn.cursor()
                
                # Verificar si existe el destinatario
                cursor.execute("SELECT id FROM usuarios WHERE username=?", (to_user,))
                if not cursor.fetchone():
                    server_socket.sendto("Usuario destinatario no existe".encode(), address)
                    conn.close()
                    continue
                
                # Verificar si el remitente está bloqueado por el destinatario
                cursor.execute("""
                    SELECT c.bloqueado 
                    FROM contactos c
                    JOIN usuarios u1 ON c.usuario_id = u1.id
                    JOIN usuarios u2 ON c.contacto_id = u2.id
                    WHERE u1.username = ? AND u2.username = ?
                """, (to_user, from_user))
                
                result = cursor.fetchone()
                conn.close()
                
                # Si está bloqueado, no entregar el mensaje
                if result and result[0] == 1:
                    server_socket.sendto("Mensaje no entregado: contacto bloqueado".encode(), address)
                # Si el destinatario está conectado, entregar el mensaje directamente
                elif to_user in connected_users:
                    # Formato de mensaje: MSG|remitente|contenido
                    full_msg = f"MSG|{from_user}|{msg}"
                    try:
                        server_socket.sendto(full_msg.encode(), connected_users[to_user])
                        server_socket.sendto("Mensaje enviado".encode(), address)
                    except Exception as e:
                        print(f"Error al enviar mensaje a {to_user}: {e}")
                        server_socket.sendto("Error al enviar mensaje".encode(), address)
                else:
                    # Si el usuario no está conectado, informar al remitente
                    server_socket.sendto("Usuario no conectado".encode(), address)
                        
        except ConnectionResetError:
            # Manejar error de conexión reset (puede ocurrir si un cliente se desconecta abruptamente)
            print("Error de conexión. Reiniciando...")
            time.sleep(1)  # Pequeña pausa para evitar consumo excesivo de CPU
        except Exception as e:
            # Capturar cualquier otra excepción para evitar que el servidor se caiga
            print(f"Error en el servidor: {e}")
            time.sleep(1)  # Pequeña pausa para evitar consumo excesivo de CPU
            
except KeyboardInterrupt:
    # Salir limpiamente con Ctrl+C
    print("Servidor detenido por el usuario")
finally:
    # Asegurar que el socket se cierre al salir
    server_socket.close()
    print("Servidor cerrado")

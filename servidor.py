import socket
import sqlite3
import time
import threading
import os
import logging
import datetime
import sys

# Configuración del socket UDP
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind(('localhost', 12345))

# Aumentar el tamaño del búfer de recepción del socket
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)

# Configuración del socket TCP para archivos
tcp_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
tcp_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

# Configuración del servidor TCP para transferencia de archivos
try:
    # Vincular al puerto e iniciar escucha
    tcp_server.bind(('localhost', 12346))
    tcp_server.listen(5)  # Permitir hasta 5 conexiones pendientes
    
except OSError as e:
    if "Address already in use" in str(e):
        pass
    sys.exit(1)
except Exception as e:
    sys.exit(1)

# Directorio para guardar archivos temporales
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Diccionario para almacenar las direcciones de usuarios conectados
# Formato: {username: dirección}
connected_users = {}

# Tamaño máximo de fragmento para envío de archivos (en bytes)
CHUNK_SIZE = 4096

# Manejador de conexiones TCP para archivos
def handle_file_transfer(client_socket, client_address):
    try:
        # Configurar timeout para la recepción inicial
        client_socket.settimeout(10.0)
        
        try:
            # Recibir encabezado/solicitud
            header = client_socket.recv(1024).decode()
            
            # Procesar según el tipo de solicitud
            if header.startswith("FILE_HEADER|"):
                # Es una solicitud para enviar un archivo al servidor
                handle_file_upload(client_socket, client_address, header)
                
            elif header.startswith("GET_FILE|"):
                # Es una solicitud para descargar un archivo
                handle_file_download(client_socket, client_address, header)
                
            else:
                try:
                    client_socket.send("ERROR|Solicitud no reconocida".encode())
                except:
                    pass
        
        except socket.timeout:
            try:
                client_socket.send("ERROR|Timeout esperando datos".encode())
            except:
                pass
            
        except Exception as e:
            try:
                client_socket.send(f"ERROR|Error interno: {str(e)}".encode())
            except:
                pass
    
    finally:
        try:
            client_socket.close()
        except:
            pass

def handle_file_upload(client_socket, client_address, header):
    """Maneja la subida de un archivo al servidor"""
    try:
        if not header.startswith("FILE_HEADER|"):
            client_socket.send("ERROR|Cabecera inválida".encode())
            return
        
        # Parsear encabezado: FILE_HEADER|from_user|to_user|file_name|file_size
        parts = header.split('|')
        if len(parts) != 5:
            client_socket.send("ERROR|Formato incorrecto".encode())
            return
        
        from_user = parts[1]
        to_user = parts[2]
        file_name = parts[3]
        file_size = int(parts[4])
        
        # Verificar si el destinatario está bloqueado
        conn = sqlite3.connect('mensajeria.db')
        cursor = conn.cursor()
        
        # Verificar si el destinatario existe
        cursor.execute("SELECT id FROM usuarios WHERE username=?", (to_user,))
        if not cursor.fetchone():
            client_socket.send("ERROR|Usuario destinatario no existe".encode())
            conn.close()
            return
        
        # Verificar si el remitente está bloqueado
        cursor.execute("""
            SELECT c.bloqueado 
            FROM contactos c
            JOIN usuarios u1 ON c.usuario_id = u1.id
            JOIN usuarios u2 ON c.contacto_id = u2.id
            WHERE u1.username = ? AND u2.username = ?
        """, (to_user, from_user))
        
        result = cursor.fetchone()
        is_blocked = result and result[0] == 1
        
        if is_blocked:
            client_socket.send("ERROR|Usuario destinatario te tiene bloqueado".encode())
            conn.close()
            return
        
        # Responder que estamos listos para recibir
        client_socket.send("READY".encode())
        
        # Crear directorio uploads si no existe
        if not os.path.exists("uploads"):
            os.makedirs("uploads")
        
        # Nombre único para el archivo
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = os.path.join("uploads", f"{timestamp}_{file_name}")
        
        # Recibir el archivo
        with open(file_path, 'wb') as file:
            total_received = 0
            start_time = time.time()
            
            # Configurar timeout para la transferencia
            client_socket.settimeout(5.0)
            
            try:
                while total_received < file_size:
                    try:
                        chunk = client_socket.recv(min(4096, file_size - total_received))
                        if not chunk:
                            break
                        
                        file.write(chunk)
                        total_received += len(chunk)
                        
                        # Mostrar progreso cada 10%
                        progress = int((total_received / file_size) * 100)
                        if progress % 10 == 0:
                            elapsed = time.time() - start_time
                            speed = total_received / elapsed if elapsed > 0 else 0
                            print(f"Progreso: {progress}% - {speed:.2f} bytes/seg")
                    except socket.timeout:
                        print("Timeout durante la recepción, continuando...")
                        continue
            except Exception as e:
                print(f"Error recibiendo archivo: {e}")
                client_socket.send("ERROR|Error durante la transferencia".encode())
                return
        
        # Verificar si se recibió todo el archivo
        if total_received < file_size:
            print(f"Transferencia incompleta: {total_received}/{file_size} bytes")
            client_socket.send("ERROR|Transferencia incompleta".encode())
            return
        
        # Guardar el archivo en la base de datos
        try:
            # Leer el archivo
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Obtener IDs de usuario
            cursor.execute("SELECT id FROM usuarios WHERE username=?", (from_user,))
            from_user_id = cursor.fetchone()[0]
            
            cursor.execute("SELECT id FROM usuarios WHERE username=?", (to_user,))
            to_user_id = cursor.fetchone()[0]
            
            # Guardar en la tabla de archivos
            cursor.execute("""
                INSERT INTO archivos (remitente_id, destinatario_id, nombre_archivo, tamano_archivo, datos, ruta_archivo)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (from_user_id, to_user_id, file_name, file_size, file_data, file_path))
            
            file_id = cursor.lastrowid
            conn.commit()
            
            # Registrar el envío en el historial
            cursor.execute("""
                INSERT INTO transferencias (archivo_id, progreso, estado)
                VALUES (?, 100, 'completado')
            """, (file_id,))
            conn.commit()
            
            print(f"Archivo guardado en la base de datos con ID {file_id}")
            
            # Enviar confirmación al cliente
            client_socket.send(f"SUCCESS|{file_id}".encode())
            
            # Notificar al destinatario si está conectado
            if to_user in connected_users:
                notificacion = f"FILE_READY|{from_user}|{file_name}|{file_size}|{file_id}"
                print(f"Enviando notificación al destinatario {to_user}: {notificacion}")
                server_socket.sendto(notificacion.encode(), connected_users[to_user])
                print(f"Notificación de archivo enviada a {to_user}")
            
        except Exception as e:
            print(f"Error guardando archivo en la base de datos: {e}")
            client_socket.send("ERROR|Error guardando archivo".encode())
        
        # Eliminar el archivo temporal
        try:
            os.remove(file_path)
        except:
            pass
        
        conn.close()
        
    except Exception as e:
        try:
            client_socket.send(f"ERROR|{str(e)}".encode())
        except:
            pass

def handle_file_download(client_socket, client_address, header):
    """Maneja la descarga de un archivo desde el servidor"""
    print(f"Procesando solicitud de descarga: {header}")
    
    try:
        # Validar formato: GET_FILE|username|file_id
        parts = header.split('|')
        if len(parts) < 3:
            print(f"Formato de solicitud incorrecto: {header}")
            client_socket.send("ERROR|Formato de solicitud incorrecto".encode())
            return
        
        username = parts[1]
        file_id = int(parts[2])
        
        print(f"Solicitud de descarga del archivo {file_id} por {username}")
        
        # Obtener información del archivo de la base de datos
        conn = sqlite3.connect('mensajeria.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT a.datos, a.nombre_archivo, a.tamano_archivo, a.remitente_id, a.destinatario_id
                FROM archivos a
                WHERE a.id = ?
            """, (file_id,))
            
            result = cursor.fetchone()
            
            if not result:
                print(f"Archivo solicitado no encontrado: ID {file_id}")
                client_socket.send("ERROR|Archivo no encontrado".encode())
                conn.close()
                return
            
            file_data, file_name, file_size, remitente_id, destinatario_id = result
            print(f"Archivo encontrado: {file_name}, tamaño: {file_size} bytes")
            
            # Verificar que file_data no sea None y tenga el tamaño correcto
            if file_data is None or len(file_data) != file_size:
                print(f"Datos inconsistentes del archivo {file_id}: tamaño esperado {file_size}, recibido {len(file_data) if file_data else 0}")
                client_socket.send("ERROR|Datos de archivo inconsistentes o corruptos".encode())
                conn.close()
                return
            
            # Verificar si el usuario tiene permisos para descargar el archivo
            cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
            user_result = cursor.fetchone()
            
            if not user_result:
                print(f"Usuario no autorizado: {username}")
                client_socket.send("ERROR|Usuario no autorizado".encode())
                conn.close()
                return
            
            user_id = user_result[0]
            
            # Verificar si el usuario es el remitente o el destinatario
            if user_id != remitente_id and user_id != destinatario_id:
                print(f"Usuario {username} no tiene permisos para descargar el archivo {file_id}")
                client_socket.send("ERROR|No tienes permisos para descargar este archivo".encode())
                conn.close()
                return
                
            # Registrar que se está descargando el archivo
            cursor.execute("""
                INSERT INTO transferencias (archivo_id, progreso, estado)
                VALUES (?, 0, 'en_progreso')
            """, (file_id,))
            conn.commit()
            
            # Establecer un timeout corto para la comunicación
            client_socket.settimeout(5.0)
            
            # Enviar confirmación al cliente
            print(f"Enviando confirmación para inicio de descarga: {file_name}")
            client_socket.sendall(f"SENDING|{file_name}|{file_size}".encode())
            
            # Esperar confirmación del cliente
            try:
                response = client_socket.recv(1024).decode()
                print(f"Respuesta del cliente para descarga: {response}")
                
                if response != "READY":
                    print(f"Cliente no está listo para recibir: {response}")
                    client_socket.sendall("ERROR|Cliente rechazó la transferencia".encode())
                    cursor.execute("""
                        UPDATE transferencias 
                        SET estado = 'fallido', fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                    """, (file_id, file_id))
                    conn.commit()
                    conn.close()
                    return
            except (socket.timeout, ConnectionResetError) as e:
                print(f"Error en la confirmación del cliente: {e}")
                cursor.execute("""
                    UPDATE transferencias 
                    SET estado = 'fallido', fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                """, (file_id, file_id))
                conn.commit()
                conn.close()
                return
            
            # Breve pausa para asegurar que el cliente está listo
            time.sleep(0.5)
            
            # Enviar el archivo
            try:
                # Leer el archivo desde la base de datos
                print(f"Iniciando envío de archivo {file_name} ({file_size} bytes)")
                
                # Asegurar que los primeros bytes se envíen correctamente
                print(f"Primeros bytes del archivo: {file_data[:20].hex() if len(file_data) >= 20 else file_data.hex()}")
                
                total_sent = 0
                chunk_size = 4096  # 4KB por fragmento
                start_time = time.time()
                last_log_time = start_time
                
                # Configurar el socket para no bloquear
                client_socket.settimeout(5.0)  # Timeout de 5 segundos
                
                try:
                    # Enviar un primer fragmento más pequeño para iniciar la transferencia
                    first_chunk_size = min(1024, file_size)  # 1KB o menos si el archivo es más pequeño
                    first_chunk = file_data[:first_chunk_size]
                    bytes_sent = client_socket.send(first_chunk)
                    total_sent = bytes_sent
                    
                    print(f"Primer fragmento enviado: {bytes_sent} bytes")
                    time.sleep(0.1)  # Pequeña pausa
                    
                    # Continuar con el resto del archivo
                    while total_sent < file_size:
                        try:
                            # Determinar cuánto enviar en este fragmento
                            remaining = file_size - total_sent
                            current_chunk_size = min(chunk_size, remaining)
                            
                            # Obtener un fragmento del archivo
                            chunk = file_data[total_sent:total_sent + current_chunk_size]
                            
                            # Enviar el fragmento
                            bytes_sent = client_socket.send(chunk)
                            
                            if bytes_sent == 0:
                                print("Conexión cerrada por el cliente durante la transferencia")
                                raise ConnectionError("Conexión cerrada por el cliente")
                            
                            # Actualizar el contador
                            total_sent += bytes_sent
                            
                            # Actualizar el progreso en la base de datos cada 5%
                            progress = int((total_sent / file_size) * 100)
                            if progress % 5 == 0 or progress == 100 or total_sent == file_size:
                                cursor.execute("""
                                    UPDATE transferencias 
                                    SET progreso = ?, fecha_actualizacion = CURRENT_TIMESTAMP
                                    WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                                """, (progress, file_id, file_id))
                                conn.commit()
                            
                            # Mostrar progreso en logs cada segundo
                            current_time = time.time()
                            if current_time - last_log_time >= 1.0:
                                elapsed = current_time - start_time
                                speed = total_sent / elapsed if elapsed > 0 else 0
                                print(f"Progreso envío: {total_sent}/{file_size} bytes ({progress}%) - {speed:.2f} bytes/seg")
                                last_log_time = current_time
                                
                            # Pequeña pausa para no saturar la red
                            if current_chunk_size >= 4096:
                                time.sleep(0.01)
                                
                        except socket.timeout:
                            # Timeout no es un error crítico, intentamos de nuevo
                            print("Timeout durante el envío, reintentando...")
                            continue
                        except (ConnectionError, BrokenPipeError) as e:
                            print(f"Error de conexión durante el envío: {e}")
                            break
                        
                    # Verificar si se envió todo el archivo
                    elapsed_time = time.time() - start_time
                    transfer_speed = file_size / elapsed_time if elapsed_time > 0 else 0
                    
                    # Registrar el resultado de la transferencia
                    if total_sent >= file_size * 0.99:  # Consideramos éxito si se envió al menos el 99%
                        # Transferencia completada con éxito
                        cursor.execute("""
                            UPDATE transferencias 
                            SET estado = 'completado', progreso = 100, fecha_actualizacion = CURRENT_TIMESTAMP
                            WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                        """, (file_id, file_id))
                        conn.commit()
                        
                        print(f"Archivo {file_name} enviado correctamente a {username}. Velocidad: {transfer_speed:.2f} bytes/seg")
                    else:
                        # Transferencia incompleta
                        cursor.execute("""
                            UPDATE transferencias 
                            SET estado = 'fallido', progreso = ?, fecha_actualizacion = CURRENT_TIMESTAMP
                            WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                        """, (int((total_sent / file_size) * 100), file_id, file_id))
                        conn.commit()
                        
                        print(f"Transferencia incompleta: {total_sent}/{file_size} bytes enviados ({(total_sent/file_size)*100:.1f}%)")
                        
                except Exception as e:
                    print(f"Error enviando el archivo: {e}")
                    cursor.execute("""
                        UPDATE transferencias 
                        SET estado = 'fallido', fecha_actualizacion = CURRENT_TIMESTAMP
                        WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                    """, (file_id, file_id))
                    conn.commit()
            
            except Exception as e:
                print(f"Error general en la transferencia: {e}")
                cursor.execute("""
                    UPDATE transferencias 
                    SET estado = 'fallido', fecha_actualizacion = CURRENT_TIMESTAMP
                    WHERE archivo_id = ? AND id = (SELECT MAX(id) FROM transferencias WHERE archivo_id = ?)
                """, (file_id, file_id))
                conn.commit()
            
            finally:
                conn.close()
                
        except Exception as e:
            print(f"Error obteniendo información del archivo: {e}")
            client_socket.send(f"ERROR|Error interno: {str(e)}".encode())
            conn.close()
            
    except Exception as e:
        print(f"Error en handle_file_download: {e}")
        try:
            client_socket.send(f"ERROR|{str(e)}".encode())
        except:
            pass

# Iniciar hilo del servidor TCP
def tcp_server_thread():
    try:
        while True:
            try:
                print("Esperando conexiones entrantes...")
                client_socket, client_address = tcp_server.accept()
                print(f"Nueva conexión TCP desde {client_address}")
                client_handler = threading.Thread(
                    target=handle_file_transfer,
                    args=(client_socket, client_address)
                )
                client_handler.daemon = True
                client_handler.start()
            except Exception as e:
                print(f"Error aceptando conexión TCP: {e}")
                time.sleep(1)  # Pequeña pausa antes de intentar de nuevo
    except Exception as e:
        pass
    finally:
        print("Cerrando servidor TCP")
        tcp_server.close()

# Iniciar servidor TCP en un hilo separado
tcp_thread = threading.Thread(target=tcp_server_thread)
tcp_thread.daemon = True
tcp_thread.start()

try:
    # Bucle principal del servidor UDP
    print("Iniciando bucle principal del servidor UDP")
    while True:
        try:
            # Recibir mensaje de cliente
            message, address = server_socket.recvfrom(65536)  # Aumentar el tamaño del búfer
            try:
                request = message.decode().split('|')  # Intentar decodificar como texto
                if len(request) > 1:
                    # No logueamos el mensaje completo si tiene contraseñas
                    if request[0] in ['LOGIN', 'REGISTER']:
                        print(f"Solicitud {request[0]} recibida desde {address} para usuario {request[1]}")
                    else:
                        print(f"Solicitud recibida: {' | '.join(request)}")
            except UnicodeDecodeError:
                request = None  # Si falla, es probable que sean datos binarios
                print(f"Datos binarios recibidos desde {address}")
            
            if request:
                # Validar longitud mínima de la solicitud
                if len(request) < 2:
                    print(f"Solicitud mal formada desde {address}: {request}")
                    server_socket.sendto("Solicitud mal formada".encode(), address)
                    continue

                # Procesar solicitudes de texto
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
                    except Exception as e:
                        server_socket.sendto(f"Error en el registro: {e}".encode(), address)
                    conn.close()

                # LOGIN DE USUARIO
                elif request[0] == 'LOGIN':
                    username, password = request[1], request[2]
                    conn = sqlite3.connect('mensajeria.db')
                    cursor = conn.cursor()
                    try:
                        # Verificar credenciales
                        cursor.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
                        if cursor.fetchone():
                            # Guardar dirección del usuario para enviar mensajes
                            connected_users[username] = address
                            
                            # Enviar respuesta de login exitoso
                            server_socket.sendto("Login exitoso".encode(), address)
                        else:
                            server_socket.sendto("Credenciales incorrectas".encode(), address)
                    except Exception as e:
                        server_socket.sendto(f"Error en el login: {e}".encode(), address)
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

                # SOLICITAR DESCARGA DE ARCHIVO
                elif request[0] == 'REQUEST_FILE':
                    username = request[1]
                    file_id = int(request[2])
                    
                    print(f"Solicitud de descarga de archivo recibida: ID {file_id} por {username}")
                    
                    # Verificar que el archivo existe
                    conn = sqlite3.connect('mensajeria.db')
                    cursor = conn.cursor()
                    
                    try:
                        # Verificar si el archivo existe
                        cursor.execute("""
                            SELECT a.id, a.nombre_archivo, a.tamano_archivo, a.remitente_id, a.destinatario_id,
                                  u1.username as remitente, u2.username as destinatario
                            FROM archivos a
                            JOIN usuarios u1 ON a.remitente_id = u1.id
                            JOIN usuarios u2 ON a.destinatario_id = u2.id
                            WHERE a.id = ?
                        """, (file_id,))
                        
                        file_info = cursor.fetchone()
                        
                        if not file_info:
                            print(f"Archivo {file_id} no encontrado para {username}")
                            server_socket.sendto("ERROR|Archivo no encontrado".encode(), address)
                            conn.close()
                            continue
                        
                        # Verificar si el usuario tiene permiso (es el remitente o el destinatario)
                        cursor.execute("SELECT id FROM usuarios WHERE username = ?", (username,))
                        user_result = cursor.fetchone()
                        
                        if not user_result:
                            print(f"Usuario {username} no autorizado para descargar el archivo {file_id}")
                            server_socket.sendto("ERROR|Usuario no autorizado".encode(), address)
                            conn.close()
                            continue
                        
                        user_id = user_result[0]
                        remitente_id = file_info[3]
                        destinatario_id = file_info[4]
                        
                        if user_id != remitente_id and user_id != destinatario_id:
                            print(f"Usuario {username} sin permisos para el archivo {file_id}")
                            server_socket.sendto("ERROR|No tienes permisos para este archivo".encode(), address)
                            conn.close()
                            continue
                        
                        # Configuración del puerto TCP para esta transferencia
                        # Usar puerto base + ID de archivo para evitar conflictos
                        transfer_tcp_port = 12346
                        
                        # Registrar la transferencia en la base de datos
                        cursor.execute("""
                            INSERT INTO transferencias (archivo_id, progreso, estado)
                            VALUES (?, 0, 'pendiente')
                        """, (file_id,))
                        conn.commit()
                        
                        response = f"FILE_TCP_PORT|{transfer_tcp_port}|{file_id}"
                        
                        # Enviar el puerto TCP al cliente
                        print(f"Enviando puerto TCP {transfer_tcp_port} a {username} para archivo {file_id}")
                        server_socket.sendto(response.encode(), address)
                        
                    except Exception as e:
                        print(f"Error procesando solicitud de archivo: {e}")
                        server_socket.sendto("ERROR|Error interno del servidor".encode(), address)
                    finally:
                        conn.close()

                # SOLICITAR INFO DE ARCHIVO
                elif request[0] == 'FILE_INFO':
                    file_id = int(request[1])
                    conn = sqlite3.connect('mensajeria.db')
                    cursor = conn.cursor()
                    
                    cursor.execute("""
                        SELECT a.nombre_archivo, a.tamano_archivo, u.username, a.fecha_envio 
                        FROM archivos a
                        JOIN usuarios u ON a.remitente_id = u.id
                        WHERE a.id = ?
                    """, (file_id,))
                    
                    result = cursor.fetchone()
                    conn.close()
                    
                    if result:
                        file_name, file_size, sender, date = result
                        info = f"FILE_INFO|{file_id}|{file_name}|{file_size}|{sender}|{date}"
                        server_socket.sendto(info.encode(), address)
                    else:
                        server_socket.sendto(f"ERROR|Archivo no encontrado".encode(), address)
                        
            else:
                print("Datos binarios recibidos")  # Depuración
                # Aquí ya no procesamos datos binarios por UDP
                        
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
    # Asegurar que los sockets se cierren al salir
    server_socket.close()
    tcp_server.close()
    print("Servidor cerrado")

import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, Menu, filedialog, ttk
import os
import time
import datetime
#me dice ola yo le digo goodbye
class ChatApp:
    def __init__(self, root):
        #Inicializa la aplicación y configura la interfaz gráfica y los socket.
        #Args:
        #   root: Ventana principal de Tkinter
        self.root = root
        self.root.title("Aplicación de Chat")
        self.root.geometry("700x500")
        self.root.resizable(True, True)
        
        # Socket UDP para la comunicación con el servidor
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket.bind(('localhost', 0))  # Puerto aleatorio
        self.server_address = ('localhost', 12345)
        
        # Configura el host y puerto TCP para transferencia de archivos
        self.tcp_host = 'localhost'
        self.tcp_port = 12346
        
        # Aumentar el tamaño del búfer de recepción del socket
        self.client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
        
        # Variables de estado
        self.username = ""  # Usuario actual
        self.logged_in = False  # Estado de la sesión
        self.contacts = []  # Lista de contactos (nombre, bloqueado)
        self.current_chat = None  # Chat actualmente seleccionado
        self.pending_tcp_port = None # Puerto TCP para la próxima descarga
        self.pending_tcp_file_id = None # ID de archivo para la próxima descarga
        
        # Hilo para recibir mensajes en background
        self.receive_thread = threading.Thread(target=self.recibir_mensajes)
        self.receive_thread.daemon = True
        self.receive_thread.start()
        
        # Crear los componentes de la interfaz
        self.create_login_frame()  # Panel de login
        self.create_main_frame()   # Panel principal (contactos + chat)
        
        # Mostrar primero la pantalla de login
        self.show_login_frame()
    
    def create_login_frame(self):
        # Crea la pantalla de login/registro inicial
        self.login_frame = tk.Frame(self.root)
        
        # Título de la aplicación
        tk.Label(self.login_frame, text="Sistema de Mensajería", font=("Arial", 16)).pack(pady=20)
        
        # Frame para botones
        button_frame = tk.Frame(self.login_frame)
        
        # Botones de login y registro
        tk.Button(button_frame, text="Iniciar Sesión", width=15, command=self.show_login_dialog).pack(side=tk.LEFT, padx=10)
        tk.Button(button_frame, text="Registrarse", width=15, command=self.show_register_dialog).pack(side=tk.LEFT, padx=10)
        
        button_frame.pack(pady=20)
    
    def create_main_frame(self):
        # Crea la pantalla principal con la lista de contactos y el área de chat
        self.main_frame = tk.Frame(self.root)
        
        # Panel izquierdo - Lista de contactos
        self.contacts_frame = tk.Frame(self.main_frame, width=200, bg="#f0f0f0")
        self.contacts_frame.pack_propagate(False)
        
        # Encabezado del panel de contactos
        tk.Label(self.contacts_frame, text="Contactos", bg="#f0f0f0", font=("Arial", 12)).pack(pady=10)
        
        # Lista de contactos con selección única
        self.contacts_listbox = tk.Listbox(self.contacts_frame, selectmode=tk.SINGLE, width=25)
        self.contacts_listbox.pack(pady=5, padx=10, fill=tk.BOTH, expand=True)
        self.contacts_listbox.bind("<<ListboxSelect>>", self.contact_selected)
        self.contacts_listbox.bind("<Button-3>", self.show_contact_menu)  # Menú contextual (clic derecho)
        
        # Botón para agregar contacto
        tk.Button(self.contacts_frame, text="Agregar Contacto", command=self.add_contact_dialog).pack(pady=10)
        
        self.contacts_frame.pack(side=tk.LEFT, fill=tk.Y)
        
        # Panel derecho - Área de chat
        self.chat_frame = tk.Frame(self.main_frame)
        
        # Área de visualización de mensajes
        self.chat_display = scrolledtext.ScrolledText(self.chat_frame, state='disabled', width=50, height=20)
        self.chat_display.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Panel para entrada de mensajes
        self.message_frame = tk.Frame(self.chat_frame)
        
        # Campo de texto para escribir mensajes
        self.message_entry = tk.Entry(self.message_frame, width=40)
        self.message_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.message_entry.bind("<Return>", self.send_message)  # Enviar con Enter
        
        # Botón de enviar mensaje
        tk.Button(self.message_frame, text="Enviar", command=self.send_message).pack(side=tk.LEFT, padx=5)
        
        # Botón para enviar archivos
        tk.Button(self.message_frame, text="Enviar Archivo", command=self.send_file_dialog).pack(side=tk.LEFT, padx=5)
        
        self.message_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.chat_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Menú contextual para la lista de contactos
        self.contact_menu = Menu(self.root, tearoff=0)
        self.contact_menu.add_command(label="Bloquear contacto", command=self.block_selected_contact)
        self.contact_menu.add_command(label="Desbloquear contacto", command=self.unblock_selected_contact)
        self.contact_menu.add_separator()
        self.contact_menu.add_command(label="Eliminar contacto", command=self.remove_selected_contact)
    
    def show_contact_menu(self, event):
        # Muestra el menú contextual al hacer clic derecho en un contacto
        selection = self.contacts_listbox.curselection()
        if selection:
            self.contacts_listbox.selection_set(selection)
            self.contact_menu.post(event.x_root, event.y_root)
    
    def block_selected_contact(self):
        # Bloquea el contacto seleccionado en la lista
        selection = self.contacts_listbox.curselection()
        if selection:
            index = selection[0]
            contact_name = self.contacts[index][0]  
            self.block_contact(contact_name)
    
    def unblock_selected_contact(self):
        # Desbloquea el contacto seleccionado en la lista
        selection = self.contacts_listbox.curselection()
        if selection:
            index = selection[0]
            contact_name = self.contacts[index][0]
            self.unblock_contact(contact_name)
    
    def remove_selected_contact(self):
        # Elimina el contacto seleccionado en la lista
        selection = self.contacts_listbox.curselection()
        if selection:
            index = selection[0]
            contact_name = self.contacts[index][0]
            if messagebox.askyesno("Confirmar", f"¿Estás seguro de eliminar el contacto {contact_name}?"):
                self.remove_contact(contact_name)
    
    def show_login_frame(self):
        # Muestra la pantalla de login
        self.main_frame.pack_forget()
        self.login_frame.pack(fill=tk.BOTH, expand=True)
    
    def show_main_frame(self):
        # Muestra la pantalla principal de chat y carga los contactos
        self.login_frame.pack_forget()
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        # Cargar contactos al iniciar sesión
        self.get_contacts()
    
    def show_login_dialog(self):
        # Muestra el diálogo para iniciar sesión
        login_dialog = tk.Toplevel(self.root)
        login_dialog.title("Iniciar Sesión")
        login_dialog.geometry("300x150")
        login_dialog.grab_set()  # Modal
        
        tk.Label(login_dialog, text="Usuario:").pack(pady=(10, 0))
        username_entry = tk.Entry(login_dialog, width=30)
        username_entry.pack(pady=5)
        
        tk.Label(login_dialog, text="Contraseña:").pack()
        password_entry = tk.Entry(login_dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        def do_login():
            # Función auxiliar para procesar el login
            username = username_entry.get()
            password = password_entry.get()
            if username and password:
                self.login(username, password)
                login_dialog.destroy()
            else:
                messagebox.showwarning("Error", "Completa todos los campos")
        
        tk.Button(login_dialog, text="Iniciar Sesión", command=do_login).pack(pady=10)
    
    def show_register_dialog(self):
        # Muestra el diálogo para registrar un nuevo usuario
        register_dialog = tk.Toplevel(self.root)
        register_dialog.title("Registrarse")
        register_dialog.geometry("300x150")
        register_dialog.grab_set()  # Modal
        
        tk.Label(register_dialog, text="Usuario:").pack(pady=(10, 0))
        username_entry = tk.Entry(register_dialog, width=30)
        username_entry.pack(pady=5)
        
        tk.Label(register_dialog, text="Contraseña:").pack()
        password_entry = tk.Entry(register_dialog, width=30, show="*")
        password_entry.pack(pady=5)
        
        def do_register():
            # Función auxiliar para procesar el registro
            username = username_entry.get()
            password = password_entry.get()
            if username and password:
                self.register(username, password)
                register_dialog.destroy()
            else:
                messagebox.showwarning("Error", "Completa todos los campos")
        
        tk.Button(register_dialog, text="Registrarse", command=do_register).pack(pady=10)
    
    def add_contact_dialog(self):
        # Muestra el diálogo para agregar un contacto
        contact = simpledialog.askstring("Agregar contacto", "Nombre de usuario:")
        if contact:
            self.add_contact(contact)
    
    # Métodos de comunicación con el servidor
    
    def login(self, username, password):
        # Envía solicitud de login al servidor
        self.client_socket.sendto(f"LOGIN|{username}|{password}".encode(), self.server_address)
        self.username = username  # Guardamos el nombre de usuario para usar más adelante
    
    def register(self, username, password):
        # Envía solicitud de registro al servidor
        self.client_socket.sendto(f"REGISTER|{username}|{password}".encode(), self.server_address)
    
    def get_contacts(self):
        # Solicita la lista de contactos del usuario al servidor
        if self.username:
            print(f"Solicitando contactos para {self.username}")
            self.client_socket.sendto(f"GET_CONTACTS|{self.username}".encode(), self.server_address)
    
    def add_contact(self, contact_name):
        # Envía solicitud para agregar contacto
        if self.username:
            self.client_socket.sendto(f"ADD_CONTACT|{self.username}|{contact_name}".encode(), self.server_address)
    
    def block_contact(self, contact_name):
        # Envía solicitud para bloquear contacto
        if self.username:
            self.client_socket.sendto(f"BLOCK_CONTACT|{self.username}|{contact_name}".encode(), self.server_address)
    
    def unblock_contact(self, contact_name):
        # Envía solicitud para desbloquear contacto
        if self.username:
            self.client_socket.sendto(f"UNBLOCK_CONTACT|{self.username}|{contact_name}".encode(), self.server_address)
    
    def remove_contact(self, contact_name):
        # Envía solicitud para eliminar contacto
        if self.username:
            self.client_socket.sendto(f"REMOVE_CONTACT|{self.username}|{contact_name}".encode(), self.server_address)
    
    # Métodos de manejo de interfaz
    
    def add_contact_to_list(self, contact_info):
        # Añade un contacto a la lista local Args: contact_info: Tupla (nombre, estado_bloqueado)
        contact_name = contact_info[0]
        blocked = contact_info[1]
    
        # Verificar si el contacto ya está en la lista
        for i, (name, _) in enumerate(self.contacts):
            if name == contact_name:
                self.contacts[i] = (contact_name, blocked)
                self.update_contacts_list()
                return
        
        self.contacts.append((contact_name, blocked))
        self.update_contacts_list()
    
    def update_contacts_list(self):
        # Actualiza la interfaz de la lista de contactos
        self.contacts_listbox.delete(0, tk.END)
        for contact_name, blocked in self.contacts:
            display_text = f"{contact_name} [BLOQUEADO]" if blocked else contact_name
            self.contacts_listbox.insert(tk.END, display_text)
    
    def contact_selected(self, event):
        # Maneja el evento de selección de contacto en la lista
        if not self.contacts_listbox.curselection():
            return
        
        index = self.contacts_listbox.curselection()[0]
        contact_name = self.contacts[index][0]
        blocked = self.contacts[index][1]
        
        # No permite chatear con contactos bloqueados
        if blocked:
            messagebox.showinfo("Contacto bloqueado", f"El contacto {contact_name} está bloqueado. Desbloquéalo para chatear.")
            return
        
        # Cambiar el contacto actual y limpiar la ventana de chat
        self.current_chat = contact_name
        self.root.title(f"Chat con {self.current_chat}")
        
        # Eliminar la marca [NUEVO] si existe
        current_text = self.contacts_listbox.get(index)
        if " [NUEVO]" in current_text:
            self.contacts_listbox.delete(index)
            cleaned_text = current_text.replace(" [NUEVO]", "")
            self.contacts_listbox.insert(index, cleaned_text)
        
        self.chat_display.config(state='normal')
        self.chat_display.delete(1.0, tk.END)
        self.chat_display.config(state='disabled')
    
    def send_message(self, event=None):
        # Envía un mensaje al contacto seleccionado Args: event: Evento de Tkinter (opcional, para bind con Enter)

        if not self.current_chat:
            messagebox.showwarning("Error", "Selecciona un contacto primero")
            return
        
        message = self.message_entry.get().strip()
        if message:
            self.client_socket.sendto(f"SEND|{self.username}|{self.current_chat}|{message}".encode(), self.server_address)
            
            # Mostrar mensaje enviado en la ventana de chat
            self.chat_display.config(state='normal')
            self.chat_display.insert(tk.END, f"Tú: {message}\n")
            self.chat_display.see(tk.END)
            self.chat_display.config(state='disabled')
            
            self.message_entry.delete(0, tk.END)
    
    def send_file_dialog(self):
        # Abre un diálogo para seleccionar un archivo y lo envía al contacto actual
        if not self.current_chat:
            messagebox.showwarning("Error", "Selecciona un contacto primero")
            return
        
        file_path = filedialog.askopenfilename(title="Seleccionar archivo")
        if file_path:
            self.send_file_tcp(file_path)

    def send_file_tcp(self, file_path):
        # Envía un archivo usando TCP al contacto actual
        if not self.current_chat:
            messagebox.showwarning("Error", "Selecciona un contacto primero")
            return
            
        try:
            # Verificar tamaño del archivo
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # Mostrar barra de progreso
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Enviando archivo")
            progress_window.geometry("300x120")
            
            tk.Label(progress_window, text=f"Enviando: {file_name}").pack(pady=(10, 5))
            tk.Label(progress_window, text=f"Tamaño: {self.format_size(file_size)}").pack(pady=5)
            
            progress_var = tk.DoubleVar()
            progress_bar = tk.Scale(progress_window, variable=progress_var, from_=0, to=100, 
                                    orient=tk.HORIZONTAL, length=250, state='disabled')
            progress_bar.pack(pady=5)
            
            status_label = tk.Label(progress_window, text="Iniciando transferencia...")
            status_label.pack(pady=5)
            
            # Actualizar la interfaz
            self.root.update()
            
            # Crear socket TCP para la transferencia
            tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tcp_socket.connect((self.tcp_host, self.tcp_port))
            
            # Enviar encabezado con información del archivo
            header = f"FILE_HEADER|{self.username}|{self.current_chat}|{file_name}|{file_size}"
            tcp_socket.send(header.encode())
            
            # Esperar confirmación del servidor
            response = tcp_socket.recv(1024).decode()
            
            if response != "READY":
                if response.startswith("ERROR|"):
                    error_msg = response.split("|")[1]
                    messagebox.showerror("Error", error_msg)
                else:
                    messagebox.showerror("Error", "El servidor no está listo para recibir el archivo")
                progress_window.destroy()
                tcp_socket.close()
                return
            
            # Enviar el archivo en fragmentos
            with open(file_path, "rb") as file:
                sent_size = 0
                start_time = time.time()
                last_update_time = start_time
                
                # Tamaño de fragmento: 4KB
                chunk_size = 4096
                
                while sent_size < file_size:
                    # Leer un fragmento del archivo
                    chunk = file.read(chunk_size)
                    if not chunk:
                        break
                    
                    # Enviar el fragmento
                    tcp_socket.send(chunk)
                    
                    # Actualizar progreso
                    sent_size += len(chunk)
                    progress_percent = int((sent_size / file_size) * 100)
                    progress_var.set(progress_percent)
                    
                    # Calcular velocidad de transferencia
                    elapsed_time = time.time() - start_time
                    current_time = time.time()
                    
                    if elapsed_time > 0:
                        speed = sent_size / elapsed_time
                        status_label.config(text=f"Enviando... {self.format_size(sent_size)}/{self.format_size(file_size)} - {self.format_size(speed)}/s")
                    
                    # Actualizar la interfaz
                    self.root.update()
                    
                    # Log cada segundo
                    if current_time - last_update_time >= 1.0:
                        last_update_time = current_time
            
            # Esperar la respuesta del servidor
            response = tcp_socket.recv(1024).decode()
            progress_window.destroy()
            
            transfer_duration = time.time() - start_time
            transfer_speed = file_size / transfer_duration if transfer_duration > 0 else 0
            
            if response.startswith("SUCCESS"):
                # Actualizar el chat con el archivo enviado
                self.chat_display.config(state='normal')
                self.chat_display.insert(tk.END, f"Tú enviaste un archivo: {file_name}\n")
                self.chat_display.see(tk.END)
                self.chat_display.config(state='disabled')
                
                messagebox.showinfo("Éxito", f"Archivo '{file_name}' enviado correctamente")
            else:
                error_msg = response.split("|")[1] if "|" in response else "Error desconocido"
                messagebox.showerror("Error", f"No se pudo enviar el archivo: {error_msg}")
            
            # Cerrar el socket TCP
            tcp_socket.close()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo enviar el archivo: {e}")
            try:
                progress_window.destroy()
            except:
                pass
            try:
                tcp_socket.close()
            except:
                pass
    
    def format_size(self, size_bytes):
        # Formatea un tamaño en bytes a formato legible
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes/(1024*1024):.1f} MB"
        else:
            return f"{size_bytes/(1024*1024*1024):.1f} GB"

    def download_file(self, file_id):
        # Solicita la descarga de un archivo por ID
        try:
            # Solicitar al servidor información sobre el archivo
            self.client_socket.sendto(f"FILE_INFO|{file_id}".encode(), self.server_address)
            
            # Los datos llegarán en la función de recibir mensajes
            messagebox.showinfo("Descarga", "Iniciando descarga del archivo...")
        except Exception as e:
            messagebox.showerror("Error", f"Error al iniciar descarga: {e}")
    
    def download_file_tcp(self, file_id, file_name, file_size):
        # Descarga un archivo por TCP
        try:
            # Determinar extensión del archivo para configurar el filtro adecuado
            extension = os.path.splitext(file_name)[1].lower()
            if not extension:
                file_types = [('Todos los archivos', '*.*')]
            else:
                # Ejemplo: Para archivos .pdf
                if extension == '.pdf':
                    file_types = [('Archivos PDF', '*.pdf'), ('Todos los archivos', '*.*')]
                elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp']:
                    file_types = [('Imágenes', f'*{extension}'), ('Todos los archivos', '*.*')]
                elif extension in ['.doc', '.docx']:
                    file_types = [('Documentos Word', f'*{extension}'), ('Todos los archivos', '*.*')]
                elif extension == '.txt':
                    file_types = [('Archivos de texto', '*.txt'), ('Todos los archivos', '*.*')]
                else:
                    file_types = [(f'Archivos {extension}', f'*{extension}'), ('Todos los archivos', '*.*')]
            
            # Abrir diálogo para seleccionar ubicación de guardado
            save_path = filedialog.asksaveasfilename(
                title=f"Guardar {file_name}",
                initialfile=file_name,
                filetypes=file_types
            )
            
            if not save_path:
                return
            
            # Ventana de progreso
            progress_window = tk.Toplevel(self.root)
            progress_window.title("Descargando archivo")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)
            
            tk.Label(progress_window, text=f"Descargando: {file_name}").pack(pady=10)
            tk.Label(progress_window, text=f"Tamaño: {self.format_size(int(file_size))}").pack(pady=5)
            
            progress_var = tk.IntVar()
            progress_bar = ttk.Progressbar(progress_window, variable=progress_var, maximum=100)
            progress_bar.pack(fill=tk.X, padx=20, pady=10)
            
            status_label = tk.Label(progress_window, text="Iniciando descarga...")
            status_label.pack(pady=5)
            
            # DEBUG: Registrar solicitud al servidor UDP
            self.client_socket.sendto(f"REQUEST_FILE|{self.username}|{file_id}".encode(), self.server_address)
            
            # Esperar a que el hilo de recepción obtenga la información del puerto TCP
            status_label.config(text="Esperando respuesta del servidor...")
            self.root.update()
            
            timeout_start = time.time()
            received_port_info = False
            tcp_port = None
            
            while time.time() - timeout_start < 10: # Esperar hasta 10 segundos
                if self.pending_tcp_port is not None and self.pending_tcp_file_id == int(file_id):
                    tcp_port = self.pending_tcp_port
                    received_port_info = True
                    # Limpiar las variables pendientes para la próxima descarga
                    self.pending_tcp_port = None
                    self.pending_tcp_file_id = None
                    break
                time.sleep(0.1) # Pequeña pausa para no consumir CPU
                self.root.update() # Mantener interfaz responsiva
            
            if not received_port_info:
                messagebox.showerror("Error", "No se recibió la información del puerto TCP del servidor.")
                progress_window.destroy()
                return
                
            # Crear un socket TCP fresco para evitar conflictos
            try:
                # Actualizar interfaz para mostrar que estamos conectando
                status_label.config(text="Conectando al servidor...")
                self.root.update()
                
                # Esperar un momento antes de intentar conectar
                time.sleep(1.0)
                
                # Conectar al servidor TCP
                tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                tcp_socket.settimeout(10.0)  # Timeout suficiente para la conexión inicial
                
                # Intentar conexión con manejo de errores
                try:
                    # Mostrar que estamos intentando conectar
                    status_label.config(text=f"Conectando a localhost:{tcp_port}...")
                    self.root.update()
                    
                    tcp_socket.connect(('localhost', tcp_port))
                except ConnectionRefusedError:
                    # Si falla la primera vez, podemos reintentarlo
                    status_label.config(text="Conexión rechazada, reintentando...")
                    self.root.update()
                    
                    time.sleep(2.0)
                    tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    tcp_socket.settimeout(10.0)
                    tcp_socket.connect(('localhost', tcp_port))
                    
                status_label.config(text="Conexión establecida")
                self.root.update()
                
                # Enviar solicitud de archivo
                request = f"GET_FILE|{self.username}|{file_id}"
                tcp_socket.sendall(request.encode())
                
                # Esperar confirmación del servidor
                try:
                    response = tcp_socket.recv(1024).decode()
                    
                    if not response.startswith("SENDING|"):
                        if response.startswith("ERROR|"):
                            error_msg = response.split("|")[1]
                            messagebox.showerror("Error", error_msg)
                        else:
                            messagebox.showerror("Error", "El servidor no está listo para enviar el archivo")
                        tcp_socket.close()
                        progress_window.destroy()
                        return
                    
                    # Enviar confirmación de que estamos listos para recibir
                    tcp_socket.sendall("READY".encode())
                    status_label.config(text="Iniciando transferencia...")
                    self.root.update()
                    
                    # Recibir archivo con modo bloqueante
                    with open(save_path, 'wb') as file:
                        received_size = 0
                        start_time = time.time()
                        last_update_time = start_time
                        last_activity_time = start_time
                        
                        # Configurar timeout suficiente para esperar a que empiece la transferencia
                        tcp_socket.settimeout(10.0)
                        
                        # Recibir el primer fragmento para confirmar inicio de transferencia
                        try:
                            first_chunk = tcp_socket.recv(4096)
                            if first_chunk:
                                file.write(first_chunk)
                                file.flush()
                                received_size += len(first_chunk)
                                last_activity_time = time.time()
                                
                                # Actualizar progreso visual
                                progress_percent = int((received_size / int(file_size)) * 100) if int(file_size) > 0 else 0
                                progress_var.set(progress_percent)
                                elapsed_time = time.time() - start_time
                                speed = received_size / elapsed_time if elapsed_time > 0 else 0
                                status_label.config(
                                    text=f"Descargando... {self.format_size(received_size)}/{self.format_size(int(file_size))} - {self.format_size(speed)}/s"
                                )
                                self.root.update()
                            else:
                                messagebox.showerror("Error", "No se recibieron datos iniciales")
                                tcp_socket.close()
                                progress_window.destroy()
                                return
                        except socket.timeout:
                            messagebox.showerror("Error", "Tiempo de espera agotado esperando los primeros datos")
                            tcp_socket.close()
                            progress_window.destroy()
                            return
                        
                        # Continuar recibiendo el resto del archivo
                        # Usar un timeout más corto para el resto de la transferencia
                        tcp_socket.settimeout(5.0)
                        
                        while received_size < int(file_size):
                            try:
                                # Comprobar si ha pasado demasiado tiempo sin actividad
                                current_time = time.time()
                                if current_time - last_activity_time > 15.0:  # 15 segundos sin datos
                                    print("Advertencia: Timeout por inactividad durante la descarga")
                                    break
                                
                                # Recibir datos
                                chunk = tcp_socket.recv(4096)
                                
                                if not chunk:
                                    print("Advertencia: Conexión cerrada por el servidor.") # Use print since logger is removed
                                    break
                                
                                # Actualizar tiempo de última actividad
                                last_activity_time = current_time
                                
                                # --- Add specific write error handling ---
                                try:
                                    file.write(chunk)
                                    file.flush()  # Asegurar que los datos se escriban en disco
                                except OSError as write_err:
                                    print(f"Error escribiendo en archivo: {write_err}") # Use print
                                    messagebox.showerror("Error de Escritura", f"No se pudo escribir en el archivo:\n{write_err}")
                                    break # Stop download on write error
                                # --- End specific write error handling ---
                                
                                # Actualizar progreso
                                received_size += len(chunk)
                                progress_percent = int((received_size / int(file_size)) * 100)
                                progress_var.set(progress_percent)
                                
                                # Actualizar interfaz cada segundo aproximadamente
                                if current_time - last_update_time >= 0.5:
                                    elapsed_time = current_time - start_time
                                    speed = received_size / elapsed_time if elapsed_time > 0 else 0
                                    status_label.config(
                                        text=f"Descargando... {self.format_size(received_size)}/{self.format_size(int(file_size))} - {self.format_size(speed)}/s"
                                    )
                                    self.root.update()
                                    # logger.debug(f"Progreso descarga: {received_size}/{file_size} bytes ({progress_percent}%) - {self.format_size(speed)}/s")
                                    last_update_time = current_time
                                
                            except socket.timeout:
                                print("Advertencia: Timeout durante la descarga, continuando...") # Use print
                                continue
                            # --- Add specific connection error handling ---
                            except ConnectionAbortedError as abort_err:
                                print(f"Error: Conexión abortada: {abort_err}") # Use print
                                break # Stop download
                            except OSError as sock_err: # Catch other socket/OS errors during recv
                                print(f"Error de socket/OS durante recv: {sock_err}") # Use print
                                break # Stop download
                            # --- End specific connection error handling ---
                            except Exception as e:
                                print(f"Error inesperado recibiendo datos: {e}") # Use print
                                break
                    
                    # Cerrar conexión
                    tcp_socket.close()
                    
                    # Cerrar ventana de progreso
                    progress_window.destroy()
                    
                    # Verificar si se descargó todo el archivo
                    transfer_duration = time.time() - start_time
                    transfer_speed = int(file_size) / transfer_duration if transfer_duration > 0 else 0
                    
                    if received_size >= int(file_size) * 0.99:  # Consideramos éxito si se recibió al menos 99%
                        messagebox.showinfo("Éxito", f"Archivo '{file_name}' descargado correctamente en:\n{save_path}")
                    else:
                        if received_size > 0:
                            if messagebox.askyesno("Descarga incompleta", 
                                                f"Se descargaron {self.format_size(received_size)} de {self.format_size(int(file_size))} ({(received_size/int(file_size))*100:.1f}%).\n¿Deseas conservar el archivo parcial?"):
                                pass
                            else:
                                try:
                                    os.remove(save_path)
                                except Exception as e:
                                    pass
                        else:
                            messagebox.showerror("Error", "Descarga fallida. No se recibieron datos del servidor.")
                except socket.timeout:
                    tcp_socket.close()
                    progress_window.destroy()
                    messagebox.showerror("Error", "Tiempo de espera agotado esperando respuesta del servidor.")
            
            except socket.timeout:
                messagebox.showerror("Error", "Tiempo de espera agotado durante la transferencia.")
                try:
                    tcp_socket.close()
                except:
                    pass
                
            except ConnectionRefusedError:
                messagebox.showerror("Error", "El servidor rechazó la conexión. Intente nuevamente.")
                try:
                    progress_window.destroy()
                except:
                    pass
        except Exception as e:
            messagebox.showerror("Error", f"Error al descargar el archivo: {e}")
            try:
                progress_window.destroy()
            except:
                pass

    def receive_file(self, sender, file_name, file_size, file_id=None):
        """Muestra el archivo recibido en el chat con un vínculo para descargarlo"""
        if file_id:
            download_command = lambda: self.download_file_tcp(file_id, file_name, file_size)
            
            # Mostrar un mensaje inmediato al usuario
            messagebox.showinfo("Nuevo archivo", 
                               f"Has recibido un archivo de {sender}:\n{file_name} ({self.format_size(int(file_size))})")
        else:
            download_command = lambda: messagebox.showinfo("Error", "No se puede descargar este archivo")
            
        link_button = tk.Button(
            self.chat_display, 
            text=f"{file_name} ({self.format_size(int(file_size))})",
            command=download_command,
            fg="blue", 
            cursor="hand2", 
            relief=tk.FLAT,
            font=("Arial", 9, "underline")
        )
        self.chat_display.window_create(tk.END, window=link_button)
        
        # Agregar hora actual
        now = datetime.datetime.now().strftime("%H:%M:%S")
        self.chat_display.insert(tk.END, f" [{now}]\n\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
        
        # Si el chat con el remitente no está actualmente abierto,
        # asegurarnos de que el usuario sepa que recibió un archivo
        if self.current_chat != sender:
            # Marcar visualmente que hay un nuevo archivo (esta implementación depende del tipo de lista)
            # Ya que estamos usando un Listbox, aquí adaptamos el código:
            try:
                for i, (name, _) in enumerate(self.contacts):
                    if name == sender:
                        # Cambiar el color o texto para indicar mensaje nuevo
                        current_text = self.contacts_listbox.get(i)
                        if not current_text.endswith(" [NUEVO]"):
                            self.contacts_listbox.delete(i)
                            self.contacts_listbox.insert(i, current_text + " [NUEVO]")
                        break
            except Exception as e:
                pass

    def display_message(self, sender, message):
        # Muestra un mensaje recibido en la ventana de chat Args: sender: Usuario que envió el mensaje ---- message: Contenido del mensaje

        self.chat_display.config(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n")
        self.chat_display.see(tk.END)
        self.chat_display.config(state='disabled')
    
    def recibir_mensajes(self):
        # Hilo principal para recibir y procesar mensajes del servidor.
        # Ejecuta continuamente en background.
        while True:
            try:
                response, _ = self.client_socket.recvfrom(65536)  # Aumentar el tamaño del búfer
                try:
                    message = response.decode(errors="ignore").strip()  # Intentar decodificar como texto y limpiar espacios
                except UnicodeDecodeError:
                    message = None  # Si falla, es probable que sean datos binarios
                
                if message:
                    # Validar que el mensaje sea texto limpio
                    if not all(32 <= ord(char) <= 126 or char in '\n\r\t' for char in message):
                        print("Mensaje descartado: contiene caracteres no válidos.")
                        continue
                    
                    print(f"Mensaje recibido: {message}")  # Depuración
                    # Procesar respuestas según el tipo de mensaje
                    if message.startswith("Login exitoso"):
                        self.logged_in = True
                        messagebox.showinfo("Éxito", "Sesión iniciada correctamente")
                        self.show_main_frame()
                    
                    elif message.startswith("Registro exitoso"):
                        messagebox.showinfo("Éxito", "Usuario registrado correctamente")
                    
                    elif message.startswith("Contacto agregado:"):
                        contact_name = message.split(":")[-1].strip()
                        messagebox.showinfo("Éxito", f"Contacto {contact_name} agregado correctamente")
                        self.add_contact_to_list((contact_name, 0))  # Añadir como no bloqueado
                    
                    elif message.startswith("Contacto bloqueado:"):
                        contact_name = message.split(":")[-1].strip()
                        messagebox.showinfo("Contacto bloqueado", f"Has bloqueado a {contact_name}")
                        # Actualizar estado en la lista de contactos
                        for i, (name, _) in enumerate(self.contacts):
                            if name == contact_name:
                                self.contacts[i] = (name, 1)  # Marcar como bloqueado
                                break
                        self.update_contacts_list()
                    
                    elif message.startswith("Contacto desbloqueado:"):
                        contact_name = message.split(":")[-1].strip()
                        messagebox.showinfo("Contacto desbloqueado", f"Has desbloqueado a {contact_name}")
                        # Actualizar estado en la lista de contactos
                        for i, (name, _) in enumerate(self.contacts):
                            if name == contact_name:
                                self.contacts[i] = (name, 0)  # Marcar como no bloqueado
                                break
                        self.update_contacts_list()
                    
                    elif message.startswith("Contacto eliminado:"):
                        contact_name = message.split(":")[-1].strip()
                        messagebox.showinfo("Contacto eliminado", f"Has eliminado a {contact_name}")
                        # Eliminar de la lista de contactos
                        self.contacts = [(name, blocked) for name, blocked in self.contacts if name != contact_name]
                        self.update_contacts_list()
                        if self.current_chat == contact_name:
                            self.current_chat = None
                            self.root.title("Aplicación de Chat")
                    
                    elif message.startswith("CONTACTS|"):
                        # Formato: CONTACTS|nombre1:estado1,nombre2:estado2,...
                        contacts_data = message.split("|")[1]
                        print(f"Datos de contactos recibidos: {contacts_data}")  # Depuración
                        
                        if contacts_data == "NONE":
                            self.contacts = []
                        else:
                            contacts_list = contacts_data.split(",")
                            self.contacts = []
                            for contact_data in contacts_list:
                                try:
                                    name, blocked = contact_data.split(":")
                                    self.contacts.append((name.strip(), int(blocked)))
                                    print(f"Contacto cargado: {name}, bloqueado: {blocked}")  # Depuración
                                except Exception as e:
                                    print(f"Error al procesar contacto {contact_data}: {e}")
                        
                        self.update_contacts_list()
                        print(f"Lista de contactos actualizada. Total: {len(self.contacts)}")  # Depuración
                    
                    elif message.startswith("MSG|"):
                        # Formato de mensajes: MSG|remitente|contenido
                        parts = message.split("|", 2)
                        if len(parts) >= 3:
                            sender = parts[1].strip()
                            content = parts[2].strip()
                            
                            # Si el remitente no está en la lista de contactos, añadirlo
                            contact_exists = False
                            for name, _ in self.contacts:
                                if name == sender:
                                    contact_exists = True
                                    break
                            
                            if not contact_exists:
                                self.add_contact_to_list((sender, 0))  # Añadir como no bloqueado
                            
                            # Si la conversación con este remitente está abierta, mostrar el mensaje
                            if self.current_chat == sender:
                                self.display_message(sender, content)
                    
                    elif message.startswith("FILE_READY|"):
                        # Formato: FILE_READY|remitente|nombre_archivo|tamaño|id_archivo
                        parts = message.split("|")
                        if len(parts) >= 5:
                            sender, file_name, file_size, file_id = parts[1], parts[2], int(parts[3]), parts[4]
                            self.receive_file(sender.strip(), file_name.strip(), file_size, file_id)
                    
                    elif message.startswith("FILE_INFO|"):
                        # Formato: FILE_INFO|id|nombre|tamaño|remitente|fecha
                        parts = message.split("|")
                        if len(parts) >= 5:
                            file_id, file_name, file_size = parts[1], parts[2], int(parts[3])
                            # Mostrar diálogo de descarga
                            self.download_file_tcp(file_id, file_name, file_size)
                    
                    elif message.startswith("FILE_TCP_PORT|"):
                        # Formato: FILE_TCP_PORT|puerto|id_archivo
                        parts = message.split("|")
                        if len(parts) >= 3:
                            try:
                                tcp_port = int(parts[1])
                                file_id = int(parts[2])
                                self.pending_tcp_port = tcp_port
                                self.pending_tcp_file_id = file_id
                            except ValueError:
                                pass
                    
                    elif message.startswith("Mensaje enviado"):
                        pass  # Ya mostramos el mensaje al enviarlo
                    
                    elif message.startswith("Mensaje no entregado"):
                        messagebox.showwarning("Mensaje no entregado", "El destinatario te ha bloqueado")
                    
                    elif message.startswith("Usuario no conectado"):
                        messagebox.showwarning("Usuario no conectado", f"El usuario '{self.current_chat}' no está conectado actualmente.")
                    
                    elif message.startswith("Mensaje guardado para entrega posterior"):
                        pass  # No mostrar notificación
                    
                    elif message.startswith("Credenciales incorrectas") or message.startswith("Usuario ya registrado"):
                        messagebox.showerror("Error", message)
                    
                    # Compatibilidad con formato antiguo para mensajes (por si hay mensajes pendientes guardados)
                    elif ":" in message and not message.startswith("MSG|"):
                        # Formato antiguo: "username: contenido del mensaje"
                        parts = message.split(":", 1)
                        if len(parts) >= 2:
                            sender = parts[0].strip()
                            content = parts[1].strip()
                            
                            # Si el remitente no está en la lista de contactos, añadirlo
                            contact_exists = False
                            for name, _ in self.contacts:
                                if name == sender:
                                    contact_exists = True
                                    break
                            
                            if not contact_exists:
                                self.add_contact_to_list((sender, 0))  # Añadir como no bloqueado
                            
                            # Si la conversación con este remitente está abierta, mostrar el mensaje
                            if self.current_chat == sender:
                                self.display_message(sender, content)
                
                else:
                    print("Datos binarios recibidos")  # Depuración
                    # En la nueva implementación, no recibiremos datos binarios por UDP
            
            except Exception as e:
                print(f"Error al recibir mensaje: {e}")

# Punto de entrada de la aplicación
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox, simpledialog, Menu

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
        
        # Variables de estado
        self.username = ""  # Usuario actual
        self.logged_in = False  # Estado de la sesión
        self.contacts = []  # Lista de contactos (nombre, bloqueado)
        self.current_chat = None  # Chat actualmente seleccionado
        
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
                response, _ = self.client_socket.recvfrom(1024)
                message = response.decode()
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
                                self.contacts.append((name, int(blocked)))
                                print(f"Contacto cargado: {name}, bloqueado: {blocked}")  # Depuración
                            except Exception as e:
                                print(f"Error al procesar contacto {contact_data}: {e}")
                    
                    self.update_contacts_list()
                    print(f"Lista de contactos actualizada. Total: {len(self.contacts)}")  # Depuración
                
                elif message.startswith("MSG|"):
                    # Formato de mensajes: MSG|remitente|contenido
                    parts = message.split("|", 2)
                    if len(parts) >= 3:
                        sender = parts[1]
                        content = parts[2]
                        
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
            
            except Exception as e:
                print(f"Error al recibir mensaje: {e}")

# Punto de entrada de la aplicación
if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop() 
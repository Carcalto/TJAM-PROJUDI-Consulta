import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading

# As funções de placeholder que existiam aqui foram removidas,
# pois a UI agora é funcional e recebe as implementações reais de callbacks do main.py.

class AppUI:
    """
    Classe principal para a Interface Gráfica do Usuário (GUI) da aplicação.
    Responsável por construir e gerenciar todos os elementos visuais e interações do usuário.
    """
    def __init__(self, root,
                 load_excel_action,
                 start_consultation_action,
                 save_credentials_action,
                 load_initial_credentials_action,
                 get_loaded_credentials_func):
        """
        Construtor da classe AppUI.

        Args:
            root: O widget raiz do Tkinter (janela principal).
            load_excel_action: Função de callback a ser chamada ao carregar arquivo Excel.
                               É fornecida pelo main.py e contém a lógica de seleção de arquivo.
            start_consultation_action: Função de callback para iniciar a consulta de processos.
                                       Fornecida pelo main.py, contém a lógica de scraping.
            save_credentials_action: Função de callback para salvar as credenciais do PROJUDI.
                                     Fornecida pelo main.py, usa o config_manager.
            load_initial_credentials_action: Função de callback para carregar credenciais iniciais.
                                             Fornecida pelo main.py, usa o config_manager.
            get_loaded_credentials_func: Função para obter credenciais já carregadas/cacheadas.
                                         Fornecida pelo main.py, obtém de config_manager.
        """
        self.root = root
        self.load_excel_action = load_excel_action
        self.start_consultation_action = start_consultation_action
        self.save_credentials_action = save_credentials_action
        self.load_initial_credentials_action = load_initial_credentials_action
        self.get_loaded_credentials_func = get_loaded_credentials_func

        self.excel_file_path = None # Armazena o caminho do arquivo Excel selecionado pelo usuário.

        self.root.title("RPA Consulta Processos TJAM") # Define o título da janela principal.
        self.root.geometry("600x450") # Define o tamanho inicial da janela.

        self._setup_ui() # Chama o método para configurar os widgets da interface.
        self._load_and_fill_credentials() # Carrega e preenche as credenciais salvas nos campos da UI.

    def _setup_ui(self):
        """
        Configura e posiciona todos os widgets da interface gráfica (botões, labels, etc.).
        Este método é chamado uma vez durante a inicialização da UI.
        """
        # --- Frame de Seleção de Arquivo Excel ---
        # Um LabelFrame é um container que pode ter um título.
        file_frame = ttk.LabelFrame(self.root, text="Seleção de Arquivo Excel")
        file_frame.pack(pady=10, padx=10, fill="x") # Empacota o frame na janela com preenchimento.

        # Label para exibir o nome do arquivo Excel selecionado.
        self.file_label = ttk.Label(file_frame, text="Nenhum arquivo selecionado")
        self.file_label.pack(side="left", padx=5, pady=5, expand=True, fill="x")

        # Botão para o usuário clicar e carregar o arquivo Excel.
        self.load_button = ttk.Button(file_frame, text="Carregar Processos", command=self._trigger_load_excel)
        self.load_button.pack(side="left", padx=5, pady=5)

        # --- Frame de Credenciais do PROJUDI ---
        cred_frame = ttk.LabelFrame(self.root, text="Credenciais PROJUDI")
        cred_frame.pack(pady=5, padx=10, fill="x")

        # Labels e campos de entrada (Entry) para usuário e senha.
        ttk.Label(cred_frame, text="Usuário:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        self.username_entry = ttk.Entry(cred_frame, width=40) # Campo para inserir o nome de usuário.
        self.username_entry.grid(row=0, column=1, padx=5, pady=2, sticky="ew")

        ttk.Label(cred_frame, text="Senha:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        self.password_entry = ttk.Entry(cred_frame, show="*", width=40) # Campo para inserir a senha (caracteres ocultos).
        self.password_entry.grid(row=1, column=1, padx=5, pady=2, sticky="ew")
        
        cred_frame.columnconfigure(1, weight=1) # Permite que a coluna dos campos de entrada expanda com a janela.

        # Botão para salvar as credenciais inseridas.
        self.save_cred_button = ttk.Button(cred_frame, text="Salvar Credenciais", command=self._trigger_save_credentials)
        self.save_cred_button.grid(row=2, column=0, columnspan=2, pady=5)

        # --- Frame de Ações (Iniciar/Resetar Consulta) ---
        action_frame = ttk.Frame(self.root) # Frame simples para agrupar botões de ação.
        action_frame.pack(pady=5, padx=10, fill="x")

        # Botão para iniciar a consulta dos processos. Inicialmente desabilitado.
        self.start_button = ttk.Button(action_frame, text="Iniciar Consulta", command=self._trigger_start_consultation, state="disabled")
        self.start_button.pack(side="left", padx=5, pady=5)

        # Botão para resetar a interface para uma nova consulta. Inicialmente desabilitado.
        self.reset_button = ttk.Button(action_frame, text="Nova Consulta", command=self._trigger_reset_gui, state="disabled")
        self.reset_button.pack(side="left", padx=5, pady=5)

        # --- Barra de Progresso ---
        self.progress_bar = ttk.Progressbar(self.root, orient="horizontal", length=580, mode="determinate")
        self.progress_bar.pack(pady=10, padx=10, fill="x")

        # --- Área de Texto para Status e Logs ---
        self.status_text = tk.Text(self.root, height=10, wrap="word") # Widget para exibir logs e mensagens de status.
        self.status_text.pack(pady=5, padx=10, fill="both", expand=True) # fill="both" e expand=True fazem o widget preencher o espaço disponível.
        
        # Adiciona uma barra de rolagem vertical ao widget de status.
        scrollbar = ttk.Scrollbar(self.status_text, orient="vertical", command=self.status_text.yview)
        self.status_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")


    def _load_and_fill_credentials(self):
        """
        Carrega as credenciais do PROJUDI (usando a função de callback `load_initial_credentials_action` fornecida)
        e preenche os campos de usuário e senha na UI, se houver credenciais salvas no config.ini.
        """
        username, password = self.load_initial_credentials_action() # Chama a ação definida em main.py
        if username:
            self.username_entry.insert(0, username)
        if password:
            self.password_entry.insert(0, password)

    def _trigger_load_excel(self):
        """
        Chamado quando o botão "Carregar Processos" é clicado.
        Executa a ação de carregamento de Excel (definida em main.py por `main_load_excel_action`)
        em uma nova thread para não bloquear a interface gráfica durante a seleção do arquivo.
        Passa os widgets relevantes da UI e um callback (`_update_excel_file_path_callback`)
        para que a ação em main.py possa atualizar o caminho do arquivo nesta classe AppUI.
        """
        threading.Thread(target=self.load_excel_action, 
                         args=(self.status_text, self.file_label, self.start_button, self.reset_button, self._update_excel_file_path_callback)).start()

    def _update_excel_file_path_callback(self, path):
        """
        Callback chamado pela `load_excel_action` (de main.py) após a seleção do arquivo.
        Atualiza o estado interno da UI (`self.excel_file_path`) e os widgets relevantes
        (label do arquivo, botões de ação, mensagem de status).

        Args:
            path (str or None): O caminho do arquivo Excel selecionado, ou None se a seleção foi cancelada.
        """
        self.excel_file_path = path
        if self.excel_file_path:
            # Atualiza a label com o nome do arquivo e habilita os botões de ação.
            self.file_label.config(text=f"Arquivo: {self.excel_file_path.split('/')[-1]}")
            self.start_button.config(state="normal")
            self.reset_button.config(state="normal")
            self.status_text.insert(tk.END, f"Arquivo {self.excel_file_path.split('/')[-1]} carregado.\n")
        else:
            # Se nenhum arquivo foi selecionado, atualiza a label e desabilita o botão de iniciar.
            self.file_label.config(text="Nenhum arquivo selecionado")
            self.start_button.config(state="disabled")
            # O botão de reset pode permanecer habilitado ou ser desabilitado, dependendo da lógica desejada.
            # Atualmente, ele é habilitado junto com o start_button se um arquivo é carregado.
            self.status_text.insert(tk.END, "Nenhum arquivo selecionado.\n")


    def _trigger_start_consultation(self):
        """
        Chamado quando o botão "Iniciar Consulta" é clicado.
        Verifica se um arquivo Excel foi carregado. Se sim, desabilita os botões de controle
        para evitar interações concorrentes e inicia a ação de consulta (definida em main.py
        por `main_start_consultation_action`) em uma nova thread.
        Passa os widgets da UI e as credenciais necessárias para a ação de consulta.
        """
        if not self.excel_file_path:
            messagebox.showwarning("Erro", "Por favor, carregue um arquivo Excel primeiro.")
            return

        # Desabilita botões para prevenir múltiplas execuções ou interações indevidas durante a consulta.
        self.start_button.config(state="disabled")
        self.load_button.config(state="disabled")
        self.reset_button.config(state="disabled")

        # Obtém as credenciais dos campos de entrada da UI.
        current_username = self.username_entry.get()
        current_password = self.password_entry.get()
        
        # Se os campos de credenciais na UI estiverem vazios, tenta usar as credenciais
        # que foram carregadas inicialmente do config.ini (via `get_loaded_credentials_func`).
        if not current_username and not current_password:
            current_username, current_password = self.get_loaded_credentials_func()

        # Executa a consulta em uma thread separada para manter a UI responsiva.
        threading.Thread(target=self.start_consultation_action,
                         args=(self.excel_file_path, self.status_text, self.progress_bar,
                               {'start': self.start_button, 'load': self.load_button, 'reset': self.reset_button}, # Mapa de botões para main.py controlar o estado.
                               (current_username, current_password)) # Credenciais a serem usadas na consulta.
                        ).start()

    def _trigger_save_credentials(self):
        """
        Chamado quando o botão "Salvar Credenciais" é clicado.
        Obtém o nome de usuário e senha dos campos de entrada da UI e chama a ação de salvar
        (definida em main.py por `main_save_credentials_action`), que por sua vez usa o config_manager.
        """
        username = self.username_entry.get()
        password = self.password_entry.get()
        self.save_credentials_action(username, password) # A ação em main.py lida com a lógica e o feedback ao usuário.

    def _trigger_reset_gui(self):
        """
        Chamado quando o botão "Nova Consulta" é clicado.
        Reseta o estado da interface para permitir uma nova seleção de arquivo e uma nova consulta.
        Limpa o caminho do arquivo, atualiza labels, reabilita/desabilita botões,
        reseta a barra de progresso e limpa a área de status.
        """
        self.excel_file_path = None # Limpa o caminho do arquivo armazenado.
        self.file_label.config(text="Nenhum arquivo selecionado")
        self.start_button.config(state="disabled")
        self.reset_button.config(state="disabled")
        self.load_button.config(state="normal") # Habilita o botão de carregar para nova seleção.
        self.progress_bar["value"] = 0 # Reseta a barra de progresso.
        self.status_text.delete(1.0, tk.END) # Limpa todo o texto da área de status.
        self.status_text.insert(tk.END, "Interface resetada. Pronto para nova consulta.\n")

def launch_ui(load_excel_action_func,
              start_consultation_action_func,
              save_credentials_action_func,
              load_initial_credentials_action_func,
              get_loaded_credentials_func_main):
    """
    Função principal para criar a janela raiz do Tkinter e iniciar a aplicação AppUI.
    Esta função é chamada pelo main.py para iniciar a interface gráfica.

    Args:
        load_excel_action_func: Referência à função em main.py para carregar Excel.
        start_consultation_action_func: Referência à função em main.py para iniciar consulta.
        save_credentials_action_func: Referência à função em main.py para salvar credenciais.
        load_initial_credentials_action_func: Referência à função em main.py para carregar credenciais iniciais.
        get_loaded_credentials_func_main: Referência à função em main.py para obter credenciais cacheadas.
    """
    root = tk.Tk() # Cria a janela principal da aplicação.
    app = AppUI(root, # Instancia a classe da UI, passando as funções de ação como callbacks.
                load_excel_action_func,
                start_consultation_action_func,
                save_credentials_action_func,
                load_initial_credentials_action_func,
                get_loaded_credentials_func_main)
    root.mainloop() # Inicia o loop de eventos do Tkinter, tornando a UI visível e interativa.

if __name__ == '__main__':
    # Este bloco é executado apenas se o arquivo ui/interface.py for rodado diretamente.
    # É útil para testar a UI de forma isolada, sem depender do main.py completo.
    # Ele não é executado quando main.py importa e chama launch_ui.
    
    # Funções de placeholder (simuladas) para permitir o teste isolado da UI.
    # Estas funções imitam o comportamento esperado das funções de ação reais do main.py.
    def test_load_excel(status_widget, label_widget, start_btn, reset_btn, path_callback):
        status_widget.insert(tk.END, "Test: Tentando carregar Excel...\n")
        # Simula a abertura de um diálogo de arquivo.
        test_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
        if test_path:
            status_widget.insert(tk.END, f"Test: Arquivo selecionado: {test_path}\n")
            path_callback(test_path) # Chama o callback da UI com o caminho.
        else:
            status_widget.insert(tk.END, "Test: Carregamento cancelado.\n")
            path_callback(None)


    def test_start_consultation(excel_path, status_widget, progress_widget, buttons, credentials):
        status_widget.insert(tk.END, f"Test: Iniciando consulta para {excel_path} com user: {credentials[0]}\n")
        for i in range(101): # Simula o progresso da consulta.
            time.sleep(0.05) # Pequena pausa para simular trabalho.
            progress_widget["value"] = i
            status_widget.insert(tk.END, f"Progresso: {i}%\n")
            status_widget.see(tk.END)
            if root_for_test: # Necessário para atualizar a UI durante o loop de teste.
                 root_for_test.update_idletasks()
        status_widget.insert(tk.END, "Test: Consulta Concluída!\n")
        # Reabilita os botões após a simulação da consulta.
        buttons['start'].config(state="normal")
        buttons['load'].config(state="normal")
        buttons['reset'].config(state="normal")


    def test_save_credentials(username, password):
        messagebox.showinfo("Test Save", f"Salvando: User={username}, Pass={password}")

    def test_load_initial_creds():
        # Simula o carregamento de credenciais que poderiam vir de um arquivo.
        return "testuser_from_config", "testpass_from_config" 
    
    def test_get_loaded_creds():
         # Simula o retorno de credenciais que já foram carregadas e estão em memória.
        return "testuser_cached", "testpass_cached"

    import time # Necessário para time.sleep no test_start_consultation.
    
    # Cria uma instância da root do Tkinter especificamente para este teste.
    # Esta variável root_for_test é usada por test_start_consultation para chamar update_idletasks,
    # o que é necessário para que as atualizações da UI sejam processadas durante a simulação.
    root_for_test = tk.Tk() 
    
    # Chama launch_ui com as funções de teste para rodar a UI em modo de teste.
    launch_ui(load_excel_action_func=test_load_excel,
              start_consultation_action_func=test_start_consultation,
              save_credentials_action_func=test_save_credentials,
              load_initial_credentials_action_func=test_load_initial_creds,
              get_loaded_credentials_func_main=test_get_loaded_creds)

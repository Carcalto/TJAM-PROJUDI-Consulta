import threading
from tkinter import filedialog, messagebox # filedialog é usado em main_load_excel_action
import tkinter as tk # Adicionado para tk.END

# Importações dos módulos de lógica de negócios
from utils.config_manager import load_credentials, save_credentials
from utils.config_manager import projudi_username as cfg_projudi_username # Para obter as credenciais carregadas
from utils.config_manager import projudi_password as cfg_projudi_password
from utils.excel_handler import read_process_numbers_from_excel, save_results_to_excel
from core.tjam_scraper import get_tjam_process_movement

# Importa a função para lançar a UI
from ui.interface import launch_ui

# Variável global para armazenar o caminho do arquivo Excel selecionado.
# Esta variável é atualizada pela UI através de um callback (`path_callback_func`)
# quando um novo arquivo é selecionado pelo usuário.
_excel_file_path_main = None

# --- Funções de Ação para a Interface Gráfica (UI) ---
# Estas funções são passadas como callbacks para a classe AppUI em ui/interface.py
# e são chamadas quando o usuário interage com os componentes da UI.

def main_load_excel_action(status_text_widget, file_label_widget, start_button_widget, reset_button_widget, path_callback_func):
    """
    Ação executada quando o usuário clica no botão para carregar um arquivo Excel.
    Abre uma caixa de diálogo para seleção de arquivo e atualiza a UI com o caminho do arquivo selecionado.

    Args:
        status_text_widget: O widget de texto da UI para exibir mensagens de status.
        file_label_widget: O widget de label da UI para exibir o nome do arquivo selecionado.
        start_button_widget: O botão "Iniciar Consulta" da UI, para habilitá-lo.
        reset_button_widget: O botão "Nova Consulta" da UI, para habilitá-lo.
        path_callback_func: Uma função da UI para ser chamada com o caminho do arquivo selecionado.
    """
    """
    Ação para carregar o arquivo Excel.
    Atualiza a UI através dos widgets fornecidos e chama o path_callback_func com o caminho.
    """
    global _excel_file_path_main
    path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
    _excel_file_path_main = path # Atualiza a variável global em main
    
    # Chama o callback fornecido pela UI para que ela possa atualizar seu estado interno e widgets
    path_callback_func(path)
    
    # A lógica de atualizar os widgets file_label, start_button, reset_button e status_text
    # agora é feita pela UI através do path_callback_func.

def main_start_consultation_action(excel_path, status_text_widget, progress_bar_widget, button_widgets_map, credentials_tuple):
    """
    Ação para iniciar a consulta dos processos.
    Lê os números dos processos do arquivo Excel, realiza o scraping para cada um,
    e atualiza a UI com o progresso e os resultados.

    Args:
        excel_path (str): O caminho para o arquivo Excel contendo os números dos processos.
        status_text_widget: Widget de texto da UI para logs.
        progress_bar_widget: Widget de barra de progresso da UI.
        button_widgets_map (dict): Um dicionário contendo os botões da UI para gerenciamento de estado.
        credentials_tuple (tuple): Uma tupla contendo (username, password) para o PROJUDI.
    """
    if not excel_path: # Verificação de segurança, embora a UI deva impedir isso.
        messagebox.showwarning("Erro", "Caminho do arquivo Excel não fornecido.")
        # Reabilitar botões na UI se necessário (a UI deve lidar com isso idealmente)
        button_widgets_map['start'].config(state="normal")
        button_widgets_map['load'].config(state="normal")
        button_widgets_map['reset'].config(state="normal")
        return

    # Limpa o status_text e reseta a barra de progresso (a UI já faz isso antes de chamar)
    # status_text_widget.delete(1.0, tk.END) # A UI já deve ter limpado
    status_text_widget.insert(tk.END, "Iniciando consulta...\n")
    progress_bar_widget["value"] = 0
    # root.update_idletasks() # Não é mais necessário, a UI lida com seus próprios updates.

    try:
        # Lê os números dos processos do arquivo Excel fornecido.
        process_numbers = read_process_numbers_from_excel(excel_path)
        if process_numbers is None:
            # Se a leitura falhar, read_process_numbers_from_excel já exibiu um erro.
            # Apenas reabilita os botões na UI e retorna.
            button_widgets_map['load'].config(state="normal")
            button_widgets_map['reset'].config(state="normal")
            return

        results = []
        total_processes = len(process_numbers)
        username, password = credentials_tuple # Desempacota as credenciais do PROJUDI.

        # Itera sobre cada número de processo para realizar a consulta.
        for i, process_number in enumerate(process_numbers):
            status_text_widget.insert(tk.END, f"Consultando processo {i+1}/{total_processes}: {process_number}\n")
            status_text_widget.see(tk.END) # Garante que a última mensagem seja visível.
            # A UI deve ser responsável por seus próprios `update_idletasks` se necessário.

            # Realiza a consulta da movimentação do processo.
            # Esta função tentará o TJAM primeiro e, se necessário, o PROJUDI.
            date, description, executed_name = get_tjam_process_movement(process_number, status_text_widget, username, password)

            # Lista de descrições que indicam falha ou ausência de dados concretos,
            # excluindo "SEGREDO DE JUSTIÇA" que é um estado válido.
            failure_indicators_date = ["N/A", "DATA NÃO ENCONTRADA"] # Convertido para upper para comparação
            failure_indicators_desc = [
                "N/A", "DESCRIÇÃO NÃO ENCONTRADA",
                "ERRO PROJUDI (LOGIN FALHOU)", "ERRO PROJUDI (USERMAINFRAME)",
                "ERRO PROJUDI (PREENCHIMENTO)", "ERRO PROJUDI (TIMEOUT MOV)",
                "ERRO PROJUDI (ELEMENTO MOV N/E)", "ERRO PROJUDI (MOVIMENTAÇÃO)",
                "N/A (PÓS-BUSCA INDEFINIDO)", "ERRO PROJUDI (TIMEOUT GERAL)",
                "ERRO PROJUDI (ELEMENTO GERAL N/E)", "ERRO PROJUDI (GERAL)",
                "NENHUM REGISTRO ENCONTRADO OU NÚMERO DE PROCESSO INVÁLIDO",
                "PROJUDI: PROCESSO NÃO LISTADO APÓS BUSCA"
            ] # Convertido para upper para comparação

            # Normaliza para maiúsculas para comparação case-insensitive
            current_date_upper = str(date).upper()
            current_description_upper = str(description).upper()
            
            # Exibe o resultado da consulta no widget de status.
            credential_error_messages = [
                "Credenciais do PROJUDI não fornecidas para a consulta.",
                "Credenciais inválidas ou problema no login."
            ]
            if description in credential_error_messages:
                status_text_widget.insert(tk.END, f"  Resultado para {process_number}: Data: {str(date)}, {str(description)}\n")
            else:
                status_text_widget.insert(tk.END, f"  Resultado para {process_number}: Data: {str(date)}, Movimentação: {str(description)}, Requerido/Executado: {str(executed_name)}\n")
            status_text_widget.insert(tk.END, "\n") # Linha em branco para separação visual.
            status_text_widget.insert(tk.END, "----------------------------------------------------------------------\n") # Linha tracejada para separação.
            status_text_widget.see(tk.END)

            # Prepara os dados para o DataFrame do Excel.
            date_upper = str(date).upper()
            description_upper = str(description).upper()
            executed_name_upper = str(executed_name).upper() # Garante que o nome do executado também seja UPPER

            results.append({
                "PROCESSO": process_number,
                "DATA_ULTIMA_MOVIMENTACAO": date_upper,
                "DESCRICAO_ULTIMA_MOVIMENTACAO": description_upper,
                "REQUERIDO/EXECUTADO": executed_name_upper # Renomeado para "REQUERIDO/EXECUTADO"
            })
            
            progress_bar_widget["value"] = (i + 1) / total_processes * 100
            # root.update_idletasks() # UI deve lidar

        # Após o loop, se houver resultados, salva-os em um arquivo Excel.
        if results:
            saved_file_path = save_results_to_excel(results) # Esta função lida com o diálogo de salvar arquivo.
            if saved_file_path:
                status_text_widget.insert(tk.END, f"Resultados salvos em: {saved_file_path}\n")
            else:
                status_text_widget.insert(tk.END, "Salvamento do arquivo de resultados cancelado ou falhou.\n")
        else:
            status_text_widget.insert(tk.END, "Nenhum resultado foi encontrado para salvar.\n")
            messagebox.showinfo("Concluído", "Consulta finalizada, mas nenhum resultado foi gerado para salvar.")

    except Exception as e:
        # Captura qualquer exceção não tratada durante o processo de consulta.
        messagebox.showerror("Erro na Consulta", f"Ocorreu um erro inesperado durante a consulta: {e}")
        status_text_widget.insert(tk.END, f"Erro: {e}\n")
    finally:
        # Reabilita os botões na UI
        button_widgets_map['start'].config(state="normal")
        button_widgets_map['load'].config(state="normal")
        button_widgets_map['reset'].config(state="normal")
        status_text_widget.insert(tk.END, "Consulta finalizada.\n")
        status_text_widget.see(tk.END)

def main_save_credentials_action(username, password):
    """Ação para salvar credenciais."""
    save_credentials(username, password) # A função save_credentials em config_manager já exibe uma messagebox.

def main_load_initial_credentials_action():
    """
    Ação para carregar as credenciais do PROJUDI armazenadas no arquivo config.ini.
    Esta função é chamada pela UI ao ser inicializada para preencher os campos de usuário e senha.
    Retorna as credenciais carregadas (username, password).
    """
    # A função load_credentials de utils.config_manager lê do arquivo .ini
    # e também atualiza as variáveis globais cfg_projudi_username e cfg_projudi_password nesse módulo.
    return load_credentials()

def main_get_loaded_credentials_func():
    """
    Fornece à UI acesso às credenciais que foram carregadas e estão em memória (cacheadas)
    no módulo config_manager. Usado se o usuário não preencher os campos na UI.
    Retorna (username, password).
    """
    return cfg_projudi_username, cfg_projudi_password


if __name__ == "__main__":
    # Ponto de entrada principal da aplicação.

    # Carrega as credenciais do PROJUDI do arquivo de configuração (config.ini) uma vez no início.
    # Isso garante que as variáveis cfg_projudi_username e cfg_projudi_password no módulo config_manager
    # sejam populadas, para que main_get_loaded_credentials_func possa retorná-las corretamente
    # e main_load_initial_credentials_action possa preencher a UI.
    load_credentials() 

    # Inicializa e executa a interface gráfica do usuário.
    # As funções de ação definidas neste arquivo são passadas para a UI,
    # permitindo que a UI acione a lógica de negócios definida aqui.
    launch_ui(
        load_excel_action_func=main_load_excel_action,
        start_consultation_action_func=main_start_consultation_action,
        save_credentials_action_func=main_save_credentials_action,
        load_initial_credentials_action_func=main_load_initial_credentials_action,
        get_loaded_credentials_func_main=main_get_loaded_credentials_func
    )

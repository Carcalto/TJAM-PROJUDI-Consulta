import threading
from tkinter import filedialog
import logging

# Importações dos módulos de lógica de negócios
from utils.config_manager import load_credentials, save_credentials
from utils.config_manager import projudi_username as cfg_projudi_username # Para obter as credenciais carregadas
from utils.config_manager import projudi_password as cfg_projudi_password
from utils.excel_handler import read_process_numbers_from_excel, save_results_to_excel
from core.tjam_scraper import get_tjam_process_movement

# Importa a função para lançar a UI
from ui.interface import launch_ui

# Importar constantes
from utils.constants import (
    EXCEL_COL_PROCESSO, EXCEL_COL_DATA_MOVIMENTACAO, EXCEL_COL_DESCRICAO_MOVIMENTACAO,
    EXCEL_COL_REQUERIDO_EXECUTADO, STATUS_NUMERO_INVALIDO, STATUS_NAO_DISPONIVEL,
    PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS, PROJUDI_ERRO_CREDENCIAIS_INVALIDAS
)

# Variável global para armazenar o caminho do arquivo Excel selecionado.
# Esta variável é atualizada pela UI através de um callback (`path_callback_func`)
# quando um novo arquivo é selecionado pelo usuário.
_excel_file_path_main = None

# --- Funções de Ação para a Interface Gráfica (UI) ---
# Estas funções são passadas como callbacks para a classe AppUI em ui/interface.py
# e são chamadas quando o usuário interage com os componentes da UI.

def main_load_excel_action(file_label_widget, start_button_widget, reset_button_widget, path_callback_func):
    """
    Ação executada quando o usuário clica no botão para carregar um arquivo Excel.
    Abre uma caixa de diálogo para seleção de arquivo e atualiza a UI com o caminho do arquivo selecionado.

    Args:
        file_label_widget: O widget de label da UI para exibir o nome do arquivo selecionado.
        start_button_widget: O botão "Iniciar Consulta" da UI, para habilitá-lo.
        reset_button_widget: O botão "Nova Consulta" da UI, para habilitá-lo.
        path_callback_func: Uma função da UI para ser chamada com o caminho do arquivo selecionado.
    """
    global _excel_file_path_main
    path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
    _excel_file_path_main = path # Atualiza a variável global em main
    
    # Chama o callback fornecido pela UI para que ela possa atualizar seu estado interno e widgets
    path_callback_func(path)
    
    # A lógica de atualizar os widgets file_label, start_button, reset_button e status_text
    # agora é feita pela UI através do path_callback_func.

def main_start_consultation_action(excel_path, progress_bar_widget, button_widgets_map, credentials_tuple):
    """
    Ação para iniciar a consulta dos processos.
    Lê os números dos processos do arquivo Excel, realiza o scraping para cada um,
    e atualiza a UI com o progresso e os resultados.

    Args:
        excel_path (str): O caminho para o arquivo Excel contendo os números dos processos.
        progress_bar_widget: Widget de barra de progresso da UI.
        button_widgets_map (dict): Um dicionário contendo os botões da UI para gerenciamento de estado.
        credentials_tuple (tuple): Uma tupla contendo (username, password) para o PROJUDI.
    """
    if not excel_path: # Verificação de segurança, embora a UI deva impedir isso.
        logging.warning("Caminho do arquivo Excel não fornecido.")
        # Reabilitar botões na UI se necessário (a UI deve lidar com isso idealmente)
        button_widgets_map['start'].config(state="normal")
        button_widgets_map['load'].config(state="normal")
        button_widgets_map['reset'].config(state="normal")
        return

    logging.info("Iniciando consulta...")
    progress_bar_widget["value"] = 0

    try:
        # Lê os números dos processos do arquivo Excel fornecido.
        valid_numbers, invalid_numbers = read_process_numbers_from_excel(excel_path)
        if valid_numbers is None:
            # Se a leitura falhar, read_process_numbers_from_excel já exibiu um um log de erro.
            # Apenas reabilita os botões na UI e retorna.
            button_widgets_map['load'].config(state="normal")
            button_widgets_map['reset'].config(state="normal")
            return

        results = []
        
        # Adiciona os números inválidos direto aos resultados sem consultar
        for invalid_num in invalid_numbers:
            results.append({
                EXCEL_COL_PROCESSO: invalid_num,
                EXCEL_COL_DATA_MOVIMENTACAO: STATUS_NAO_DISPONIVEL,
                EXCEL_COL_DESCRICAO_MOVIMENTACAO: STATUS_NUMERO_INVALIDO,
                EXCEL_COL_REQUERIDO_EXECUTADO: STATUS_NAO_DISPONIVEL
            })
            logging.info(f"Processo {invalid_num}: {STATUS_NUMERO_INVALIDO}")
            logging.info("----------------------------------------------------------------------")

        # Processa apenas os números válidos
        process_numbers = valid_numbers
        total_processes = len(process_numbers) + len(invalid_numbers)
        username, password = credentials_tuple # Desempacota as credenciais do PROJUDI.

        # Itera sobre cada número de processo para realizar a consulta.
        for i, process_number in enumerate(process_numbers):
            logging.info(f"Consultando processo {i+1}/{total_processes}: {process_number}")

            # Realiza a consulta da movimentação do processo.
            # Esta função tentará o TJAM primeiro e, se necessário, o PROJUDI.
            # O status_text_widget foi removido como argumento.
            date, description, executed_name = get_tjam_process_movement(process_number, username, password)

            # Prepara os dados para o DataFrame do Excel.
            date_display = str(date)
            description_display = str(description)
            executed_name_display = str(executed_name)

            # Usar as constantes PROJUDI_ERRO_CREDENCIAIS_...
            credential_error_messages = [
                PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS,
                PROJUDI_ERRO_CREDENCIAIS_INVALIDAS
            ]

            if description_display in credential_error_messages:
                logging.info(f"  Resultado para {process_number}: Data: {date_display}, {description_display}")
            else:
                logging.info(f"  Resultado para {process_number}: Data: {date_display}, Movimentação: {description_display}, Requerido/Executado: {executed_name_display}")
            logging.info("----------------------------------------------------------------------")

            results.append({
                EXCEL_COL_PROCESSO: process_number,
                EXCEL_COL_DATA_MOVIMENTACAO: date_display,
                EXCEL_COL_DESCRICAO_MOVIMENTACAO: description_display,
                EXCEL_COL_REQUERIDO_EXECUTADO: executed_name_display
            })
            
            # Ajusta o cálculo da barra de progresso para considerar processos inválidos já processados
            progresso_atual = len(invalid_numbers) + (i + 1)
            progress_bar_widget["value"] = progresso_atual / total_processes * 100

        # Após o loop, se houver resultados, salva-os em um arquivo Excel.
        if results:
            # O save_results_to_excel agora usará o sistema de logging
            saved_file_path = save_results_to_excel(results)
            if saved_file_path:
                logging.info(f"Resultados salvos em: {saved_file_path}")
            else:
                logging.warning("Salvamento do arquivo de resultados cancelado ou falhou.")
        else:
            logging.info("Nenhum resultado foi encontrado para salvar.")
            # A messagebox de "Concluído" agora será um log, para manter o desacoplamento.
            logging.info("Consulta finalizada, mas nenhum resultado foi gerado para salvar.")


    except Exception as e:
        # Captura qualquer exceção não tratada durante o processo de consulta.
        logging.error(f"Ocorreu um erro inesperado durante a consulta: {e}", exc_info=True)
    finally:
        # Reabilita os botões na UI
        button_widgets_map['start'].config(state="normal")
        button_widgets_map['load'].config(state="normal")
        button_widgets_map['reset'].config(state="normal")
        logging.info("Consulta finalizada.")

def main_save_credentials_action(username, password):
    """Ação para salvar credenciais."""
    # A função save_credentials em config_manager agora usa logging
    save_credentials(username, password)

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

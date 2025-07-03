import logging 
import os # Adicionar import do módulo os
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException

# Importar o ProjudiScraper que contém as Page Objects
from core.projudi_pages import ProjudiScraper

# Importar constantes
from utils.constants import (
    PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS, STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_WEBDRIVER,
    PROJUDI_ERRO_GERAL
)

# Classe de filtro para suprimir mensagens de erro de conexão específicas
class ConnectionErrorFilter(logging.Filter):
    def filter(self, record):
        # Suprime mensagens de 'NewConnectionError' que contêm 'WinError 10061'
        if 'NewConnectionError' in record.getMessage() and 'WinError 10061' in record.getMessage():
            return False # Não processa esta mensagem de log
        return True # Processa todas as outras mensagens

# Aplicar o filtro ao logger 'urllib3'
# As mensagens de NewConnectionError geralmente vêm deste logger.
logging.getLogger("urllib3").addFilter(ConnectionErrorFilter())

logger = logging.getLogger(__name__)

# Suprimir logs de urllib3 e selenium
logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("selenium").setLevel(logging.CRITICAL)

def get_projudi_process_movement(process_number, username, password):
    """
    Orquestra a consulta da movimentação de um processo no portal PROJUDI do TJAM,
    utilizando as classes de Page Object para interação com o navegador.

    Args:
        process_number (str): O número do processo a ser consultado.
        username (str): Nome de usuário para login no PROJUDI.
        password (str): Senha para login no PROJUDI.

    Returns:
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao, nome_executado).
               Retorna strings indicativas de erro ou "N/A" em caso de falha.
    """
    if not username or not password:
        logger.warning(PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS, STATUS_NAO_DISPONIVEL

    driver = None
    try:
        # --- Configuração do WebDriver (Selenium) ---
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") # Recomentar para execução silenciosa
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-extensions")
        options.page_load_strategy = 'eager'
        
        log_path = os.devnull 
        
        service_args_list = ['--log-level=OFF']

        service = ChromeService(
            ChromeDriverManager().install(),
            log_path=log_path, 
            service_args=service_args_list
        )
        
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10) # Segundos que o driver aguardará elementos
        
        projudi_scraper = ProjudiScraper(driver)
        date, description, executed_name = projudi_scraper.get_movement(process_number, username, password)
        
        return date, description, executed_name

    except WebDriverException as wde:
        logger.error(f"Erro do WebDriver ao consultar PROJUDI para {process_number}: {wde}", exc_info=True)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_WEBDRIVER, STATUS_NAO_DISPONIVEL
    except Exception as e:
        logger.error(f"Erro geral ao consultar PROJUDI para {process_number} com Selenium: {e}", exc_info=True)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_GERAL, STATUS_NAO_DISPONIVEL
    finally:
        if driver:
            try:
                driver.quit()
            except WebDriverException as e:
                logger.warning(f"Aviso: Erro ao fechar o driver do Selenium para {process_number}: {e}")

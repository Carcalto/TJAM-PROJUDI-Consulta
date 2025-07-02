# Este módulo é responsável por gerenciar as credenciais do PROJUDI,
# lendo-as e salvando-as em um arquivo de configuração (config.ini).
import configparser # Para manipulação de arquivos .ini.
import logging # Importar o módulo logging
import keyring # Para gerenciamento seguro de credenciais
import os # Para verificar o ambiente local

# Nome do serviço para o keyring
KEYRING_SERVICE_NAME = "RPA_TJAM_PROJUDI"

# Variáveis globais para armazenar em memória as credenciais carregadas.
projudi_username = ""
projudi_password = ""

def load_credentials():
    """
    Carrega as credenciais do PROJUDI do sistema de armazenamento seguro (keyring).
    Fallback para config.ini se keyring não estiver disponível ou não tiver as credenciais.
    """
    global projudi_username, projudi_password
    
    # Tenta carregar do keyring primeiro
    if keyring:
        try:
            stored_username = keyring.get_password(KEYRING_SERVICE_NAME, "username")
            stored_password = keyring.get_password(KEYRING_SERVICE_NAME, "password")
            
            if stored_username and stored_password:
                projudi_username = stored_username
                projudi_password = stored_password
                logging.info("Credenciais do PROJUDI carregadas com sucesso do sistema de armazenamento seguro.")
                return projudi_username, projudi_password
            else:
                logging.info("Credenciais do PROJUDI não encontradas no sistema de armazenamento seguro. Tentando config.ini...")
        except Exception as e:
            logging.warning(f"Erro ao tentar carregar credenciais do keyring: {e}. Certifique-se de que o keyring está configurado corretamente. Tentando config.ini como fallback.")
    else:
        logging.warning("Módulo 'keyring' não disponível ou não configurado. As credenciais não serão salvas de forma segura. Tentando config.ini como fallback.")


    # Fallback para config.ini (com aviso, pois é menos seguro)
    CONFIG_FILE = "config.ini"
    config = configparser.ConfigParser()
    if config.read(CONFIG_FILE):
        if 'PROJUDI' in config:
            projudi_username = config['PROJUDI'].get('username', '')
            projudi_password = config['PROJUDI'].get('password', '')
            if projudi_username or projudi_password:
                 logging.warning("Credenciais do PROJUDI carregadas de 'config.ini'. Considere usar o 'keyring' para maior segurança.")
        else:
            logging.info("'[PROJUDI]' seção não encontrada em config.ini.")
    else:
        logging.info("Arquivo 'config.ini' não encontrado.")
    
    return projudi_username, projudi_password

def save_credentials(username, password):
    """
    Salva as credenciais do PROJUDI no sistema de armazenamento seguro (keyring).
    Se o keyring não estiver disponível, salva em config.ini (com aviso).
    """
    global projudi_username, projudi_password
    projudi_username = username
    projudi_password = password

    if keyring:
        try:
            keyring.set_password(KEYRING_SERVICE_NAME, "username", username)
            keyring.set_password(KEYRING_SERVICE_NAME, "password", password)
            logging.info("Suas credenciais do PROJUDI foram salvas com sucesso no sistema de armazenamento seguro!")
            return # Sai da função após salvar com sucesso no keyring
        except Exception as e:
            logging.error(f"Erro ao tentar salvar credenciais no keyring: {e}. Certifique-se de que o keyring está configurado corretamente. Tentando salvar em config.ini como fallback (NÃO SEGURO).", exc_info=True)
    else:
        logging.warning("Módulo 'keyring' não disponível ou não configurado. As credenciais serão salvas em 'config.ini' (NÃO SEGURO).")

    # Fallback para salvar em config.ini (NÃO SEGURO)
    CONFIG_FILE = "config.ini"
    config = configparser.ConfigParser()
    config['PROJUDI'] = {'username': username, 'password': password}
    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        logging.info("Suas credenciais do PROJUDI foram salvas em 'config.ini'.")
    except Exception as e:
        logging.error(f"Erro ao salvar credenciais em 'config.ini': {e}", exc_info=True)

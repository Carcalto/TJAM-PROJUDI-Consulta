# Este módulo é responsável por gerenciar as credenciais do PROJUDI,
# lendo-as e salvando-as em um arquivo de configuração (config.ini).
import configparser # Para manipulação de arquivos .ini.
import tkinter as tk # Usado aqui apenas para exibir messagebox.
from tkinter import messagebox # Para exibir caixas de diálogo de informação/erro.

# Nome do arquivo de configuração onde as credenciais são armazenadas.
CONFIG_FILE = "config.ini"

# Variáveis globais para armazenar em memória as credenciais carregadas.
# Elas são atualizadas por load_credentials() e save_credentials().
projudi_username = ""
projudi_password = ""

def load_credentials():
    """Carrega as credenciais do PROJUDI do arquivo de configuração."""
    global projudi_username, projudi_password
    config = configparser.ConfigParser()
    if config.read(CONFIG_FILE):
        if 'PROJUDI' in config:
            projudi_username = config['PROJUDI'].get('username', '')
            projudi_password = config['PROJUDI'].get('password', '')
        else:
            pass
    else:
        pass
    return projudi_username, projudi_password

def save_credentials(username, password):
    """Salva as credenciais do PROJUDI no arquivo de configuração."""
    global projudi_username, projudi_password
    projudi_username = username
    projudi_password = password
    config = configparser.ConfigParser()
    config['PROJUDI'] = {'username': username, 'password': password}
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    messagebox.showinfo("Credenciais Salvas", "Suas credenciais do PROJUDI foram salvas com sucesso no arquivo config.ini!")

import tkinter as tk # Para status_text_widget.insert, idealmente seria um callback ou logger
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import time
import os
import re # Adicionado para limpeza de texto

# As credenciais serão passadas como argumento para a função principal
# ou carregadas de uma forma mais centralizada se necessário no futuro.

def get_projudi_process_movement(process_number, username, password, status_text_widget):
    """
    Consulta a movimentação de um processo diretamente no portal PROJUDI do TJAM, utilizando Selenium
    para automação do navegador. Esta função lida com o login, navegação pelos menus,
    busca do processo e extração da data e descrição da última movimentação.

    Args:
        process_number (str): O número do processo a ser consultado.
        username (str): Nome de usuário para login no PROJUDI.
        password (str): Senha para login no PROJUDI.
        status_text_widget: O widget de texto da UI para exibir mensagens de status e logs.

    Returns:
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao).
               Retorna strings indicativas de erro (ex: "Erro PROJUDI (Login Falhou)")
               ou "N/A" em caso de falha na consulta ou se o processo não for encontrado.
               Para processos em "Segredo de Justiça", retorna ("", "SEGREDO DE JUSTIÇA").
    """
    # Verifica se as credenciais foram fornecidas.
    if not username or not password:
        status_text_widget.insert(tk.END, "Credenciais do PROJUDI não fornecidas para a consulta.\n")
        return "N/A", "N/A"

    driver = None # Inicializa a variável do driver do Selenium.
    try:
        # --- Configuração do WebDriver (Selenium) ---
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") # Executa o Chrome em modo headless (sem interface gráfica visível).
        options.add_argument("--start-maximized") # Inicia maximizado (útil mesmo em headless para layout).
        options.add_argument("--log-level=3") # Define o nível de log do Chrome para suprimir mensagens.
        options.add_experimental_option('excludeSwitches', ['enable-logging']) # Tenta desabilitar logs do Chrome.
        options.add_argument("--disable-gpu") # Desabilita a aceleração por GPU (recomendado para headless).
        options.add_argument("--window-size=1920,1080") # Define um tamanho de janela virtual.
        
        # Define o caminho para onde os logs do ChromeDriver serão direcionados (dev/null ou nul).
        log_path = os.devnull # Padrão para Linux/macOS.
        if os.name == 'nt': # Se for Windows.
            log_path = 'nul'
        
        # Argumentos para o serviço do ChromeDriver para tentar desligar logs.
        service_args_list = ['--log-level=OFF']

        # Inicializa o serviço do ChromeDriver, usando webdriver_manager para baixar/gerenciar o driver.
        service = ChromeService(
            ChromeDriverManager().install(), 
            log_path=log_path, # Redireciona logs do serviço.
            service_args=service_args_list # Passa argumentos para o serviço.
        )
        # Inicializa o WebDriver do Chrome com o serviço e as opções configuradas.
        driver = webdriver.Chrome(service=service, options=options)

        # --- Etapa 1: Navegação e Login ---
        driver.get("https://projudi.tjam.jus.br/projudi/") # Acessa a página de login do PROJUDI.
        time.sleep(3) # Pausa para garantir o carregamento completo da página inicial.

        # O PROJUDI usa iframes. É necessário mudar o foco do Selenium para o iframe correto.
        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        # Preenche o campo de login.
        login_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='login']")))
        login_field.clear()
        login_field.send_keys(username)

        # Preenche o campo de senha.
        password_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='senha']")))
        password_field.clear()
        password_field.send_keys(password)

        # Clica no botão de "Entrar".
        enter_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='btEntrar']")))
        enter_button.click()
        time.sleep(3) # Pausa para o processamento do login.

        # --- Verificação de Erro de Login ---
        # Tenta identificar mensagens de erro comuns na página após a tentativa de login.
        try:
            possible_error_messages = [
                "//font[@color='red']", # Mensagens de erro geralmente em vermelho.
                "//*[contains(text(),'Usuário ou senha inválida')]",
                "//*[contains(text(),'Login inválido')]",
                "//*[contains(text(),'Problemas no login')]"
            ]
            error_found = False
            for error_xpath in possible_error_messages:
                try:
                    error_element = driver.find_element(By.XPATH, error_xpath)
                    if error_element.is_displayed():
                        status_text_widget.insert(tk.END, f"Possível erro de login no PROJUDI: {error_element.text}\n")
                        error_found = True
                        break # Para ao encontrar a primeira mensagem de erro.
                except NoSuchElementException:
                    continue # Se o XPath não for encontrado, tenta o próximo.
            
            if error_found:
                return "Erro PROJUDI (Login Falhou)", "Credenciais inválidas ou problema no login."

        except Exception as e_login_check:
            # Se a verificação de erro de login em si falhar, apenas loga um aviso.
            status_text_widget.insert(tk.END, f"Aviso: Verificação de erro de login encontrou um problema: {e_login_check}\n")

        # --- Etapa 2: Navegação pelo Menu (após login bem-sucedido) ---
        # IDs dos elementos do menu (estes podem mudar se o site for atualizado).
        menu_buscas_id = "Stm0p0i7eTX"  # ID do item de menu "Buscas".
        processos_1_grau_menu_item_id = "Stm0p7i0e" # ID do submenu "Processos 1º Grau".

        # Move o mouse para o menu "Buscas" para torná-lo visível (hover).
        menu_buscas_element = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, menu_buscas_id)))
        ActionChains(driver).move_to_element(menu_buscas_element).perform()
        time.sleep(1.5) # Pausa para o submenu aparecer.

        # Clica no submenu "Processos 1º Grau".
        processos_1_grau_element = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, processos_1_grau_menu_item_id)))
        processos_1_grau_element.click()
        
        # --- Etapa 3: Mudança de Foco para iFrames e Busca do Processo ---
        # Após clicar no menu, a página carrega conteúdo em iframes aninhados.
        driver.switch_to.default_content() # Volta para o contexto principal da página.
        time.sleep(2) # Pausa para transição.

        # Muda novamente para o 'mainFrame'.
        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        # Tenta mudar para o iframe 'userMainFrame', onde o campo de busca do processo está.
        try:
            WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
        except TimeoutException:
            status_text_widget.insert(tk.END, "Timeout: Não foi possível focar no 'userMainFrame'. A busca pode falhar.\n")
            return "Erro PROJUDI (userMainFrame)", "Erro PROJUDI (userMainFrame)"

        # Preenche o campo com o número do processo.
        numero_processo_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "numeroProcesso")))
        numero_processo_field.clear()
        numero_processo_field.send_keys(process_number)
        
        # Verificação robusta do preenchimento (às vezes send_keys pode falhar).
        current_value = numero_processo_field.get_attribute('value')
        if current_value != process_number:
            driver.execute_script(f"arguments[0].value = '{process_number}';", numero_processo_field) # Tenta com JavaScript.
            current_value = numero_processo_field.get_attribute('value')
            if current_value != process_number:
                status_text_widget.insert(tk.END, "Falha ao preencher 'numeroProcesso'.\n")
                return "Erro PROJUDI (Preenchimento)", "Erro PROJUDI (Preenchimento)"
        time.sleep(1) # Pequena pausa após preencher.

        # Clica no botão de pesquisar.
        search_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "pesquisar")))
        try:
            search_button.click()
        except Exception: # Se o clique padrão falhar, tenta com JavaScript.
            driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(2.5) # Pausa um pouco maior para a página de resultados carregar.

        # --- Etapa 4: Verificação de Resultados da Busca e Extração ---

        # Primeiro, verifica se a busca resultou em "Nenhum registro encontrado".
        try:
            # Espera um pouco para o elemento aparecer, se for o caso.
            no_records_element = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Nenhum registro encontrado')]"))
            )
            if no_records_element: # Se o elemento for encontrado e visível
                status_text_widget.insert(tk.END, f"PROJUDI: Nenhum registro encontrado para o processo {process_number}.\n")
                return "N/A", "NENHUM REGISTRO ENCONTRADO PROJUDI"
        except TimeoutException:
            # Se "Nenhum registro encontrado" não estiver visível após 5 segundos, continua.
            pass
        except NoSuchElementException:
            # Se o elemento não existir, continua.
            pass
        
        # Se não encontrou "Nenhum registro encontrado", aguarda a presença do número do processo na tabela.
        # Isso indica que a busca retornou pelo menos um resultado válido.
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{process_number}']")))
        except TimeoutException:
            # Se o número do processo não aparecer na tabela após a busca (e não foi "Nenhum registro encontrado"),
            # pode ser um erro inesperado, uma página diferente, ou o processo realmente não existe de forma listável.
            status_text_widget.insert(tk.END, f"PROJUDI: Processo {process_number} não encontrado na tabela de resultados após busca (Timeout esperando link do processo).\n")
            # Retornamos um erro genérico aqui, que será tratado no main.py
            return "N/A", "PROJUDI: PROCESSO NÃO LISTADO APÓS BUSCA"

        # Agora, verifica se o processo é "Segredo de Justiça".
        # Esta verificação ocorre após confirmar que o processo foi listado (ou seja, não é "Nenhum registro encontrado").
        try:
            segredo_justica_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Segredo de Justiça')]")
            # Verifica se o elemento encontrado está visível, para evitar falsos positivos de texto oculto.
            if segredo_justica_element and segredo_justica_element.is_displayed(): 
                status_text_widget.insert(tk.END, f"Processo {process_number} em Segredo de Justiça.\n")
                return "", "SEGREDO DE JUSTIÇA" # Retorna indicação de segredo de justiça.
        except NoSuchElementException:
            # Se não for segredo de justiça, prossegue para clicar no processo e extrair movimentações.
            pass # Continua para a tentativa de extração normal.
            
        # Se não for "Nenhum registro encontrado" nem "Segredo de Justiça", tenta extrair a movimentação.
        # Isso implica que o link do processo (com o número do processo) foi encontrado.
        try:
            # Encontra e clica no link do processo na tabela de resultados.
            process_link_td = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, f"//td[normalize-space()='{process_number}']"))
            )
            try: # O link pode estar dentro de uma tag <a> ou ser o próprio <td>.
                process_link = process_link_td.find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                process_link = process_link_td 
            
            process_link.click() # Clica para abrir os detalhes do processo.

            # Aguarda o carregamento da página de movimentações.
            # O ID 'mov1Grau,SERVIDOR,,SEMARQUIVO,,' parece ser um identificador de linha de movimentação.
            last_mov_row_id = "mov1Grau,SERVIDOR,,SEMARQUIVO,," 
            
            WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.ID, last_mov_row_id)))
            last_mov_row = driver.find_element(By.ID, last_mov_row_id) # Obtém a linha da última movimentação.
            
            # Extrai a data/hora da terceira célula (td[3]) da linha.
            date_time_element = last_mov_row.find_element(By.XPATH, ".//td[3]") 
            full_date_time_text = date_time_element.text.strip().replace('\n', ' ') # Limpa o texto.
            # Extrai apenas a parte da data (DD/MM/AAAA).
            date_part = full_date_time_text.split(" ")[0] if " " in full_date_time_text else full_date_time_text

            # Extrai a descrição da movimentação da quarta célula (td[4]), dentro de uma tag <b>.
            dizeres_element = last_mov_row.find_element(By.XPATH, ".//td[4]/b") 
            raw_dizeres_text = dizeres_element.text.strip()
            # Limpa a descrição, removendo espaços extras e quebras de linha.
            dizeres_text = re.sub(r'\s+', ' ', raw_dizeres_text).strip()
            
            status_text_widget.insert(tk.END, f"Última movimentação para {process_number}: {date_part} - {dizeres_text}\n")
            return date_part, dizeres_text # Retorna a data e a descrição limpas.

        except TimeoutException:
            status_text_widget.insert(tk.END, f"Timeout ao tentar acessar ou extrair movimentação do processo {process_number}.\n")
            return "Erro PROJUDI (Timeout Mov)", "Erro PROJUDI (Timeout Mov)"
        except NoSuchElementException:
            status_text_widget.insert(tk.END, f"Elemento da movimentação não encontrado para {process_number}.\n")
            return "Erro PROJUDI (Elemento Mov N/E)", "Erro PROJUDI (Elemento Mov N/E)"
        except Exception as e_mov:
            status_text_widget.insert(tk.END, f"Erro inesperado ao processar movimentação de {process_number}: {e_mov}\n")
            return "Erro PROJUDI (Movimentação)", "Erro PROJUDI (Movimentação)"
        
        # Se chegou aqui, algo não previsto ocorreu após a busca (nem segredo de justiça, nem link clicável).
        status_text_widget.insert(tk.END, f"Não foi possível determinar o estado do processo {process_number} após a busca.\n")
        return "N/A (Pós-Busca Indefinido)", "N/A (Pós-Busca Indefinido)"

    except TimeoutException as te:
        # Captura timeouts gerais durante a interação com o PROJUDI.
        status_text_widget.insert(tk.END, f"Timeout geral ao interagir com PROJUDI para {process_number}: {te}\n")
        return "Erro PROJUDI (Timeout Geral)", "Erro PROJUDI (Timeout Geral)"
    except NoSuchElementException as nse:
        # Captura erros de elemento não encontrado.
        status_text_widget.insert(tk.END, f"Elemento não encontrado na página do PROJUDI para {process_number}: {nse}.\n")
        return "Erro PROJUDI (Elemento Geral N/E)", "Erro PROJUDI (Elemento Geral N/E)"
    except Exception as e:
        # Captura qualquer outra exceção geral durante a consulta ao PROJUDI.
        status_text_widget.insert(tk.END, f"Erro geral ao consultar PROJUDI para {process_number} com Selenium: {e}\n")
        return "Erro PROJUDI (Geral)", "Erro PROJUDI (Geral)"
    finally:
        # Garante que o navegador seja fechado, mesmo se ocorrerem erros.
        if driver:
            driver.quit()

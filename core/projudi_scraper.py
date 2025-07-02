import logging 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
import time
import os
import re

# Importar constantes
from utils.constants import (
    STATUS_NAO_DISPONIVEL, STATUS_SEGREDO_JUSTICA, STATUS_MOVIMENTACAO_NAO_ENCONTRADA,
    PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS, PROJUDI_ERRO_CREDENCIAIS_INVALIDAS,
    PROJUDI_ERRO_USERMAINFRAME, PROJUDI_ERRO_PREENCHIMENTO, PROJUDI_PROCESS_NAO_ENCONTRADO,
    PROJUDI_PROCESS_NAO_LISTADO_POS_BUSCA, PROJUDI_ERRO_TIMEOUT_TABELA,
    PROJUDI_ERRO_NENHUMA_MOVIMENTACAO_ENCONTRADA, PROJUDI_ERRO_ELEMENTO_N_E, PROJUDI_ERRO_EXTRACAO,
    PROJUDI_ERRO_TIMEOUT_MOV, PROJUDI_ERRO_ELEMENTO_MOV_N_E, PROJUDI_ERRO_ELEMENTO_OBSOLETO,
    PROJUDI_ERRO_MOVIMENTACAO, PROJUDI_ERRO_TIMEOUT_GERAL, PROJUDI_ERRO_ELEMENTO_GERAL_N_E,
    PROJUDI_ERRO_WEBDRIVER, PROJUDI_ERRO_GERAL,
    SLEEP_LOGIN_PROJUDI, SLEEP_MENU_PROJUDI, SLEEP_FRAME_CHANGE_PROJUDI, SLEEP_FIELD_FILL_PROJUDI,
    SLEEP_SEARCH_PROJUDI, SLEEP_TABLE_RETRY, SLEEP_PAGE_LOAD, SLEEP_AFTER_PROJUDI_CONSULTA # Adicionando SLEEP_AFTER_PROJUDI_CONSULTA
)

logger = logging.getLogger(__name__) # Instanciar um logger para este módulo

def get_projudi_process_movement(process_number, username, password):
    """
    Consulta a movimentação de um processo diretamente no portal PROJUDI do TJAM, utilizando Selenium
    para automação do navegador. Esta função lida com o login, navegação pelos menus,
    busca do processo e extração da data e descrição da última movimentação.

    Args:
        process_number (str): O número do processo a ser consultado.
        username (str): Nome de usuário para login no PROJUDI.
        password (str): Senha para login no PROJUDI.

    Returns:
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao, nome_executado).
               Retorna strings indicativas de erro (ex: "Erro PROJUDI (Login Falhou)")
               ou "N/A" em caso de falha na consulta ou se o processo não for encontrado.
               Para processos em "Segredo de Justiça", retorna ("", "SEGREDO DE JUSTIÇA", "N/A").
    """
    if not username or not password:
        logger.warning(PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_CREDENCIAIS_NAO_FORNECIDAS, STATUS_NAO_DISPONIVEL

    driver = None
    try:
        # --- Configuração do WebDriver (Selenium) com otimizações ---
        options = webdriver.ChromeOptions()
        options.add_argument("--headless") # Navegador invisível para execução em produção
        options.add_argument("--start-maximized")
        options.add_argument("--log-level=3")
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # Configurações adicionais para melhorar o desempenho
        options.add_argument("--disable-dev-shm-usage") # Evita erros de memória compartilhada em sistemas com pouca RAM
        options.add_argument("--no-sandbox") # Desativa o sandbox para melhorar desempenho
        options.add_argument("--disable-extensions") # Desativa extensões para melhorar desempenho
        
        # Para carregar páginas mais rapidamente
        options.page_load_strategy = 'eager' # 'eager' carrega o DOM sem esperar por recursos como imagens
        
        log_path = os.devnull
        if os.name == 'nt':
            log_path = 'nul'
        
        service_args_list = ['--log-level=OFF']

        service = ChromeService(
            ChromeDriverManager().install(),
            log_path=log_path,
            service_args=service_args_list
        )
        
        driver = webdriver.Chrome(service=service, options=options)
        
        # Configurar timeout implícito global (último recurso para encontrar elementos)
        driver.implicitly_wait(10) # Segundos que o driver aguardará elementos (só afeta find_element)

        # --- Etapa 1: Navegação e Login ---
        driver.get("https://projudi.tjam.jus.br/projudi/")
        time.sleep(SLEEP_LOGIN_PROJUDI) # Aumentado para 5 segundos para garantir carregamento da página inicial

        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        login_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='login']")))
        login_field.clear()
        login_field.send_keys(username)

        password_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='senha']")))
        password_field.clear()
        password_field.send_keys(password)

        enter_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='btEntrar']")))
        enter_button.click()
        time.sleep(SLEEP_LOGIN_PROJUDI) # Aumentado para 5 segundos para garantir carregamento após login

        # --- Verificação de Erro de Login ---
        try:
            possible_error_messages = [
                "//font[@color='red']",
                "//*[contains(text(),'Usuário ou senha inválida')]",
                "//*[contains(text(),'Login inválido')]",
                "//*[contains(text(),'Problemas no login')]"
            ]
            error_found = False
            for error_xpath in possible_error_messages:
                try:
                    error_element = driver.find_element(By.XPATH, error_xpath)
                    if error_element.is_displayed():
                        logger.warning(f"Possível erro de login no PROJUDI: %s", error_element.text)
                        error_found = True
                        break
                except NoSuchElementException:
                    continue
            
            if error_found:
                return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_CREDENCIAIS_INVALIDAS, STATUS_NAO_DISPONIVEL

        except Exception as e_login_check:
            logger.warning(f"Aviso: Verificação de erro de login encontrou um problema: %s", e_login_check)

        # --- Etapa 2: Navegação pelo Menu (após login bem-sucedido) ---
        menu_buscas_id = "Stm0p0i7eTX"
        processos_1_grau_menu_item_id = "Stm0p7i0e"

        menu_buscas_element = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, menu_buscas_id)))
        ActionChains(driver).move_to_element(menu_buscas_element).perform()
        time.sleep(SLEEP_MENU_PROJUDI) # Aumentado para 3 segundos para garantir abertura do menu dropdown

        processos_1_grau_element = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, processos_1_grau_menu_item_id)))
        processos_1_grau_element.click()
        
        # --- Etapa 3: Mudança de Foco para iFrames e Busca do Processo ---
        driver.switch_to.default_content()
        time.sleep(SLEEP_FRAME_CHANGE_PROJUDI) # Aumentado para 4 segundos para garantir mudança de contexto após clicar no menu

        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        try:
            WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
        except TimeoutException:
            logger.error(f"Timeout: Não foi possível focar no \'userMainFrame\'. A busca pode falhar para o processo %s.", process_number)
            return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_USERMAINFRAME, STATUS_NAO_DISPONIVEL

        numero_processo_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "numeroProcesso")))
        numero_processo_field.clear()
        numero_processo_field.send_keys(process_number)
        
        current_value = numero_processo_field.get_attribute('value')
        if current_value != process_number:
            driver.execute_script(f"arguments[0].value = '{process_number}';", numero_processo_field)
            current_value = numero_processo_field.get_attribute('value')
            if current_value != process_number:
                logger.error("Falha ao preencher \'numeroProcesso\' para o processo %s.", process_number)
                return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_PREENCHIMENTO, STATUS_NAO_DISPONIVEL
        time.sleep(SLEEP_FIELD_FILL_PROJUDI) # Aumentado para 2 segundos após preenchimento do número do processo

        search_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "pesquisar")))
        try:
            search_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(SLEEP_SEARCH_PROJUDI) # Aumentado para 4 segundos para garantir tempo suficiente após clicar em pesquisar

        # --- Etapa 4: Verificação de Resultados da Busca e Extração ---

        # Primeiro, verifica se a busca resultou em "Nenhum registro encontrado".
        try:
            no_records_element = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Nenhum registro encontrado')]"))
            )
            if no_records_element:
                logger.info(f"PROJUDI: Nenhum registro encontrado para o processo %s.", process_number)
                return STATUS_NAO_DISPONIVEL, PROJUDI_PROCESS_NAO_ENCONTRADO, STATUS_NAO_DISPONIVEL
        except TimeoutException:
            pass
        except NoSuchElementException:
            pass
        
        # Se não encontrou "Nenhum registro encontrado", aguarda a presença do número do processo na tabela.
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{process_number}']")))
        except TimeoutException:
            logger.warning(f"PROJUDI: Processo %s não encontrado na tabela de resultados após busca (Timeout esperando link do processo).", process_number)
            return STATUS_NAO_DISPONIVEL, PROJUDI_PROCESS_NAO_LISTADO_POS_BUSCA, STATUS_NAO_DISPONIVEL

        # Inicializa o nome do executado; será preenchido aqui na página de resultados.
        executed_name = STATUS_NAO_DISPONIVEL
        is_segredo_justica = False

        # **********************************************
        # Função unificada para extrair informações da linha do processo:
        # - NOME DO EXECUTADO/REQUERIDO
        # - Status "SEGREDO DE JUSTIÇA"
        # Implementação baseada no código JS fornecido pelo usuário.
        # **********************************************
        def extrair_dados_da_linha_processo(linha_tr):
            """
            Extrai dados de uma linha de processo, incluindo nome do requerido/executado
            e se é segredo de justiça.
            
            Args:
                linha_tr: Elemento TR da linha do processo
                
            Returns:
                tuple: (nome_executado, is_segredo_justica)
            """
            nome_executado = STATUS_NAO_DISPONIVEL
            segredo = False
            
            try:
                # Obter todas as células (TD) da linha
                all_cells = linha_tr.find_elements(By.TAG_NAME, "td")
                
                # Verificar se é segredo de justiça em qualquer célula
                for cell in all_cells:
                    cell_text = cell.text.strip()
                    if STATUS_SEGREDO_JUSTICA in cell_text:
                        segredo = True
                        break
                
                # Se for segredo de justiça, não precisamos procurar mais
                if segredo:
                    return STATUS_NAO_DISPONIVEL, True
                    
                # Procura especificamente por "Requerido:" na estrutura da tabela
                if len(all_cells) > 2:
                    terceira_coluna = all_cells[2]
                    
                    # Procurar pela tabela.form que contém os dados das partes
                    table_forms = terceira_coluna.find_elements(By.CSS_SELECTOR, "table.form")
                    if table_forms:
                        table_form = table_forms[0]
                        
                        # Agora procurar especificamente a linha que contém "Requerido:"
                        try:
                            requerido_font = table_form.find_element(By.XPATH, ".//font[contains(text(), 'Requerido:')]")
                            if requerido_font:
                                # Subir para o elemento pai (td) e depois para o pai desse (tr)
                                requerido_td = requerido_font.find_element(By.XPATH, "./..")
                                requerido_tr = requerido_td.find_element(By.XPATH, "./..")
                                
                                # Na mesma linha (tr), pegar a segunda célula (td) que tem o nome
                                td_with_name = requerido_tr.find_elements(By.TAG_NAME, "td")[1]
                                
                                # Agora pegar o texto do <li> dentro do <ul> nessa célula
                                li_elements = td_with_name.find_elements(By.TAG_NAME, "li")
                                if li_elements and li_elements[0].text.strip():
                                    nome_executado = li_elements[0].text.strip()
                                    logger.info(f"Requerido encontrado: %s", nome_executado)
                        except NoSuchElementException:
                            # Se não encontrar com essa abordagem, continua com o próximo método
                            pass
                
                # Abordagem alternativa: procurar por células com labels específicos
                exec_labels = ["Requerido:", "Executado:", "Réu:", "Embargante:"]
                
                for i, cell in enumerate(all_cells):
                    cell_text = cell.text.strip()
                    
                    for label in exec_labels:
                        if label.replace(":", "") in cell_text:
                            # Se o label está nesta célula, o nome está na próxima
                            if (i + 1) < len(all_cells):
                                next_cell = all_cells[i + 1]
                                
                                # Procurar por UL e LI na próxima célula
                                uls = next_cell.find_elements(By.TAG_NAME, "ul")
                                if uls:
                                    lis = uls[0].find_elements(By.TAG_NAME, "li")
                                    if lis and lis[0].text.strip():
                                        nome_executado = lis[0].text.strip()
                                        break
                        
                    if nome_executado != STATUS_NAO_DISPONIVEL:
                        break
                
                # Limpar o nome do executado se encontrado
                if nome_executado != STATUS_NAO_DISPONIVEL:
                    nome_executado = re.sub(r'advogad[oa]:\s*.*', '', nome_executado, flags=re.IGNORECASE).strip()
                    nome_executado = re.sub(r"^\(parte\s+\w+\):\s*", "", nome_executado, flags=re.IGNORECASE).strip()
                    nome_executado = re.sub(r'\s+', ' ', nome_executado).strip()  # Normaliza espaços
                
                return nome_executado, segredo
                
            except Exception as e:
                logger.error(f"Erro ao extrair dados da linha do processo: %s", e)
                return STATUS_NAO_DISPONIVEL, False
        
        try:
            # Encontrar a linha (TR) do processo na tabela de resultados
            process_row_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{process_number}']//ancestor::tr[1]"))
            )
            
            # Extrair dados utilizando a função unificada
            extracted_name, is_segredo_justica = extrair_dados_da_linha_processo(process_row_element)
            
            if extracted_name != STATUS_NAO_DISPONIVEL:
                executed_name = extracted_name
                
            # Verificar segredo de justiça diretamente na página também (abordagem anterior)
            if not is_segredo_justica:
                try:
                    segredo_justica_element = driver.find_element(By.XPATH, "//*[contains(text(), 'Segredo de Justiça')]")
                    if segredo_justica_element and segredo_justica_element.is_displayed():
                        is_segredo_justica = True
                except NoSuchElementException:
                    pass  # Não é Segredo de Justiça
            
            # Se for segredo de justiça, retornar imediatamente
            if is_segredo_justica:
                logger.info(f"Processo %s em Segredo de Justiça.", process_number)
                return STATUS_NAO_DISPONIVEL, STATUS_SEGREDO_JUSTICA, executed_name
                
        except NoSuchElementException as nse:
            logger.warning(f"Aviso (PROJUDI): Elemento do executado ou de sua linha não encontrado na página de resultados para %s: %s.", process_number, nse)
        except Exception as e_exec:
            logger.warning(f"Aviso (PROJUDI): Erro inesperado ao extrair dados na página de resultados para %s: %s", process_number, e_exec)
            
        # **********************************************
        # Lógica para extrair a data e descrição da última movimentação na PÁGINA DE DETALHES.
        # Implementação baseada no código JS fornecido pelo usuário e na estrutura HTML identificada.
        # **********************************************
        date = STATUS_NAO_DISPONIVEL
        description = STATUS_MOVIMENTACAO_NAO_ENCONTRADA
        try:
            # Encontra e clica no link do processo na tabela de resultados.
            process_link_td = WebDriverWait(driver, 20).until(
                EC.element_to_be_clickable((By.XPATH, f"//td[normalize-space()='{process_number}']"))
            )
            try:
                process_link = process_link_td.find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                process_link = process_link_td
            
            process_link.click()
            # A JS function não tem sleeps aqui, então vamos usar um tempo mínimo para a mudança de página.
            time.sleep(SLEEP_AFTER_PROJUDI_CONSULTA) # Tempo suficiente para o navegador começar a carregar a nova página (ou iframe).
 
             # A tabela resultTable está diretamente no userMainFrame - simplificando a navegação
            logger.info(f"Buscando tabela de movimentações para %s...", process_number)
            
            # Garantimos que estamos no frame correto
            try:
                # Voltamos ao contexto principal
                driver.switch_to.default_content()
                
                # Navegamos diretamente para o caminho de frames necessário
                WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
                WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
                
                # Sem mensagens redundantes, apenas confirma que está pronto
                logger.info("Pronto para extrair dados da tabela.")
            except TimeoutException:
                logger.warning("Timeout ao navegar para o frame da tabela. Tentando continuar.")
            except Exception as e_frame:
                logger.warning(f"Erro ao navegar para o frame: %s. Tentando continuar.", str(e_frame)[:50])
            
            # Espera adicional para garantir carregamento completo
            time.sleep(SLEEP_PAGE_LOAD)
            
            # Implementação fiel do script JavaScript fornecido pelo usuário
            # para encontrar a última movimentação processual na tabela de movimentações
            
            # Aguardar um pouco mais antes de procurar a tabela - pode estar carregando dinamicamente
            time.sleep(SLEEP_PAGE_LOAD)  # Espera adicional para garantir o carregamento da página
            
            logger.info(f"Buscando tabela de movimentações para %s...", process_number)
            
            # 1. Selecionar a tabela de movimentações com retry
            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                try:
                    attempt += 1
                    logger.info(f"Tentativa %s de localizar tabela de movimentações...", attempt)
                    
                    # Ajustando o timeout para 45 segundos conforme solicitado
                    tabela_movimentacoes_tbody = WebDriverWait(driver, 45).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.resultTable tbody"))
                    )
                    
                    if not tabela_movimentacoes_tbody:
                        if attempt < max_attempts:
                            logger.info(f"Tabela não encontrada. Tentando novamente (%s/%s)...", attempt, max_attempts)
                            time.sleep(SLEEP_TABLE_RETRY)  # Espera entre tentativas
                            continue
                        else:
                            logger.error(f"Tabela de movimentações não encontrada após %s tentativas para %s.", max_attempts, process_number)
                            return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_TABELA_MOVIMENTACAO_N_E, executed_name
                    
                    logger.info("Tabela de movimentações encontrada! Extraindo dados...")
                    
                    # 2. Selecionar a primeira linha <tr> dentro do tbody (movimentação mais recente)
                    primeira_linha_mov = tabela_movimentacoes_tbody.find_element(By.TAG_NAME, "tr")
                    
                    if not primeira_linha_mov:
                        logger.info(f"Nenhuma linha de movimentação encontrada para %s.", process_number)
                        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_NENHUMA_MOVIMENTACAO_ENCONTRADA, executed_name
                    
                    # Inicializar variáveis
                    date = STATUS_NAO_DISPONIVEL
                    description = STATUS_MOVIMENTACAO_NAO_ENCONTRADA
                    
                    # 3. Extrair a data: está na terceira coluna (índice 2)
                    all_cells = primeira_linha_mov.find_elements(By.TAG_NAME, "td")
                    if all_cells and len(all_cells) > 2:
                        coluna_data = all_cells[2]
                        texto_data = coluna_data.text.strip()
                        logger.info(f"Texto da data encontrado: %s", texto_data)
                        match_data = re.search(r'\d{2}\/\d{2}\/\d{4}', texto_data)
                        if match_data:
                            date = match_data.group(0)
                            logger.info(f"Data extraída: %s", date)
                    
                    # 4. Extrair o evento/descrição da movimentação: está na quarta coluna (índice 3)
                    if all_cells and len(all_cells) > 3:
                        coluna_evento = all_cells[3]
                        evento_element = coluna_evento.find_element(By.TAG_NAME, "b")
                        if evento_element:
                            description = evento_element.text.strip()
                            logger.info(f"Descrição extraída: %s", description)
                    
                    # Verifica se ambos os dados foram encontrados
                    if date == STATUS_NAO_DISPONIVEL or description == STATUS_MOVIMENTACAO_NAO_ENCONTRADA:
                        logger.warning("Não foi possível extrair completamente os dados da movimentação.")
                    
                    # Se chegou até aqui, encontrou a tabela e tentou extrair os dados
                    break
                    
                except TimeoutException:
                    if attempt < max_attempts:
                        logger.warning(f"Timeout ao buscar tabela. Tentativa %s/%s. Tentando novamente...", attempt, max_attempts)
                        # Tentar fazer scroll para baixo para ajudar a carregar a tabela
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(SLEEP_TABLE_RETRY)
                    else:
                        logger.error(f"Timeout final ao buscar tabela de movimentações após %s tentativas para %s.", max_attempts, process_number)
                        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_TIMEOUT_TABELA, executed_name
                
                except NoSuchElementException as nse:
                    logger.error(f"Elemento não encontrado ao extrair movimentação (tentativa %s/%s) para %s: %s", attempt, max_attempts, process_number, nse)
                    if attempt < max_attempts:
                        time.sleep(SLEEP_TABLE_RETRY)  # Espera entre tentativas
                    else:
                        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_ELEMENTO_N_E, executed_name
                
                except Exception as e:
                    logger.error(f"Erro ao extrair movimentação (tentativa %s/%s) para %s: %s", attempt, max_attempts, process_number, e)
                    if attempt < max_attempts:
                        time.sleep(SLEEP_TABLE_RETRY)  # Espera entre tentativas
                    else:
                        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_EXTRACAO, executed_name
            
        except TimeoutException:
            logger.error(f"Erro PROJUDI (Timeout Mov) para %s.", process_number)
            date = PROJUDI_ERRO_TIMEOUT_MOV
            description = PROJUDI_ERRO_TIMEOUT_MOV
        except NoSuchElementException:
            logger.error(f"Elemento da movimentação não encontrado para %s.", process_number)
            date = PROJUDI_ERRO_ELEMENTO_MOV_N_E
            description = PROJUDI_ERRO_ELEMENTO_MOV_N_E
        except StaleElementReferenceException as sere: # Capturar erro de elemento obsoleto
            logger.warning(f"Aviso (PROJUDI): Elemento obsoleto ao extrair movimentação para %s: %s", process_number, sere)
            date = PROJUDI_ERRO_ELEMENTO_OBSOLETO
            description = PROJUDI_ERRO_ELEMENTO_OBSOLETO
        except Exception as e_mov:
            logger.error(f"Erro inesperado ao processar movimentação de %s: %s", process_number, e_mov)
            date = PROJUDI_ERRO_MOVIMENTACAO
            description = PROJUDI_ERRO_MOVIMENTACAO
        
        return date, description, executed_name
 
    except TimeoutException as te:
        logger.error(f"Timeout geral ao interagir com PROJUDI para %s: %s", process_number, te)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_TIMEOUT_GERAL, STATUS_NAO_DISPONIVEL
    except NoSuchElementException as nse:
        logger.error(f"Elemento não encontrado na página do PROJUDI para %s: %s.", process_number, nse)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_ELEMENTO_GERAL_N_E, STATUS_NAO_DISPONIVEL
    except WebDriverException as wde:
        logger.error(f"Erro do WebDriver ao consultar PROJUDI para %s: %s", process_number, wde)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_WEBDRIVER, STATUS_NAO_DISPONIVEL
    except Exception as e:
        logger.error(f"Erro geral ao consultar PROJUDI para %s com Selenium: %s", process_number, e)
        return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_GERAL, STATUS_NAO_DISPONIVEL
    finally:
        if driver:
            try:
                driver.quit()
            except WebDriverException as e:
                logger.warning(f"Aviso: Erro ao fechar o driver do Selenium para %s: %s", process_number, e)

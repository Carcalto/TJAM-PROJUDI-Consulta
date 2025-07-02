import tkinter as tk
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
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao, nome_executado).
               Retorna strings indicativas de erro (ex: "Erro PROJUDI (Login Falhou)")
               ou "N/A" em caso de falha na consulta ou se o processo não for encontrado.
               Para processos em "Segredo de Justiça", retorna ("", "SEGREDO DE JUSTIÇA", "N/A").
    """
    if not username or not password:
        status_text_widget.insert(tk.END, "Credenciais do PROJUDI não fornecidas para a consulta.\n")
        return "N/A", "Credenciais do PROJUDI não fornecidas para a consulta."

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
        time.sleep(5) # Aumentado para 5 segundos para garantir carregamento da página inicial

        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        login_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='login']")))
        login_field.clear()
        login_field.send_keys(username)

        password_field = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@id='senha']")))
        password_field.clear()
        password_field.send_keys(password)

        enter_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//input[@id='btEntrar']")))
        enter_button.click()
        time.sleep(5) # Aumentado para 5 segundos para garantir carregamento após login

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
                        status_text_widget.insert(tk.END, f"Possível erro de login no PROJUDI: {error_element.text}\n")
                        error_found = True
                        break
                except NoSuchElementException:
                    continue
            
            if error_found:
                return "N/A", "Credenciais inválidas ou problema no login.", "N/A"

        except Exception as e_login_check:
            status_text_widget.insert(tk.END, f"Aviso: Verificação de erro de login encontrou um problema: {e_login_check}\n")

        # --- Etapa 2: Navegação pelo Menu (após login bem-sucedido) ---
        menu_buscas_id = "Stm0p0i7eTX"
        processos_1_grau_menu_item_id = "Stm0p7i0e"

        menu_buscas_element = WebDriverWait(driver, 20).until(EC.visibility_of_element_located((By.ID, menu_buscas_id)))
        ActionChains(driver).move_to_element(menu_buscas_element).perform()
        time.sleep(3) # Aumentado para 3 segundos para garantir abertura do menu dropdown

        processos_1_grau_element = WebDriverWait(driver, 20).until(EC.element_to_be_clickable((By.ID, processos_1_grau_menu_item_id)))
        processos_1_grau_element.click()
        
        # --- Etapa 3: Mudança de Foco para iFrames e Busca do Processo ---
        driver.switch_to.default_content()
        time.sleep(4) # Aumentado para 4 segundos para garantir mudança de contexto após clicar no menu

        WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        try:
            WebDriverWait(driver, 30).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
        except TimeoutException:
            status_text_widget.insert(tk.END, f"Timeout: Não foi possível focar no 'userMainFrame'. A busca pode falhar.\n")
            return "N/A", "Erro PROJUDI (userMainFrame)", "N/A"

        numero_processo_field = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "numeroProcesso")))
        numero_processo_field.clear()
        numero_processo_field.send_keys(process_number)
        
        current_value = numero_processo_field.get_attribute('value')
        if current_value != process_number:
            driver.execute_script(f"arguments[0].value = '{process_number}';", numero_processo_field)
            current_value = numero_processo_field.get_attribute('value')
            if current_value != process_number:
                status_text_widget.insert(tk.END, "Falha ao preencher 'numeroProcesso'.\n")
                return "N/A", "Erro PROJUDI (Preenchimento)", "N/A"
        time.sleep(2) # Aumentado para 2 segundos após preenchimento do número do processo

        search_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.ID, "pesquisar")))
        try:
            search_button.click()
        except Exception:
            driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(4) # Aumentado para 4 segundos para garantir tempo suficiente após clicar em pesquisar

        # --- Etapa 4: Verificação de Resultados da Busca e Extração ---

        # Primeiro, verifica se a busca resultou em "Nenhum registro encontrado".
        try:
            no_records_element = WebDriverWait(driver, 5).until(
                EC.visibility_of_element_located((By.XPATH, "//*[contains(text(), 'Nenhum registro encontrado')]"))
            )
            if no_records_element:
                status_text_widget.insert(tk.END, f"PROJUDI: Nenhum registro encontrado para o processo {process_number}.\n")
                return "N/A", "NENHUM REGISTRO ENCONTRADO OU NÚMERO DE PROCESSO INVÁLIDO", "N/A"
        except TimeoutException:
            pass
        except NoSuchElementException:
            pass
        
        # Se não encontrou "Nenhum registro encontrado", aguarda a presença do número do processo na tabela.
        try:
            WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{process_number}']")))
        except TimeoutException:
            status_text_widget.insert(tk.END, f"PROJUDI: Processo {process_number} não encontrado na tabela de resultados após busca (Timeout esperando link do processo).\n")
            return "N/A", "PROJUDI: PROCESSO NÃO LISTADO APÓS BUSCA", "N/A"

        # Inicializa o nome do executado; será preenchido aqui na página de resultados.
        executed_name = "N/A"
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
            nome_executado = "N/A"
            segredo = False
            
            try:
                # Obter todas as células (TD) da linha
                all_cells = linha_tr.find_elements(By.TAG_NAME, "td")
                
                # Verificar se é segredo de justiça em qualquer célula
                for cell in all_cells:
                    cell_text = cell.text.strip()
                    if "Segredo de Justiça" in cell_text:
                        segredo = True
                        break
                
                # Se for segredo de justiça, não precisamos procurar mais
                if segredo:
                    return "N/A", True
                    
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
                                    status_text_widget.insert(tk.END, f"Requerido encontrado: {nome_executado}\n")
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
                        
                    if nome_executado != "N/A":
                        break
                
                # Limpar o nome do executado se encontrado
                if nome_executado != "N/A":
                    nome_executado = re.sub(r'advogad[oa]:\s*.*', '', nome_executado, flags=re.IGNORECASE).strip()
                    nome_executado = re.sub(r"^\(parte\s+\w+\):\s*", "", nome_executado, flags=re.IGNORECASE).strip()
                    nome_executado = re.sub(r'\s+', ' ', nome_executado).strip()  # Normaliza espaços
                
                return nome_executado, segredo
                
            except Exception as e:
                return "N/A", False
        
        try:
            # Encontrar a linha (TR) do processo na tabela de resultados
            process_row_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, f"//td[normalize-space()='{process_number}']//ancestor::tr[1]"))
            )
            
            # Extrair dados utilizando a função unificada
            extracted_name, is_segredo_justica = extrair_dados_da_linha_processo(process_row_element)
            
            if extracted_name != "N/A":
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
                status_text_widget.insert(tk.END, f"Processo {process_number} em Segredo de Justiça.\n")
                return "N/A", "SEGREDO DE JUSTIÇA", executed_name
                
        except NoSuchElementException as nse:
            status_text_widget.insert(tk.END, f"Aviso (PROJUDI): Elemento do executado ou de sua linha não encontrado na página de resultados para {process_number}: {nse}.\n")
        except Exception as e_exec:
            status_text_widget.insert(tk.END, f"Aviso (PROJUDI): Erro inesperado ao extrair dados na página de resultados para {process_number}: {e_exec}\n")
            
        # **********************************************
        # Lógica para extrair a data e descrição da última movimentação na PÁGINA DE DETALHES.
        # Implementação baseada no código JS fornecido pelo usuário e na estrutura HTML identificada.
        # **********************************************
        date = "N/A"
        description = "MOVIMENTAÇÃO NÃO ENCONTRADA"
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
            time.sleep(3) # Tempo suficiente para o navegador começar a carregar a nova página (ou iframe).

            # A tabela resultTable está diretamente no userMainFrame - simplificando a navegação
            status_text_widget.insert(tk.END, f"Buscando tabela de movimentações para {process_number}...\n")
            
            # Garantimos que estamos no frame correto
            try:
                # Voltamos ao contexto principal
                driver.switch_to.default_content()
                
                # Navegamos diretamente para o caminho de frames necessário
                WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
                WebDriverWait(driver, 20).until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
                
                # Sem mensagens redundantes, apenas confirma que está pronto
                status_text_widget.insert(tk.END, f"Pronto para extrair dados da tabela.\n")
            except TimeoutException:
                status_text_widget.insert(tk.END, f"Timeout ao navegar para o frame da tabela. Tentando continuar.\n")
            except Exception as e_frame:
                status_text_widget.insert(tk.END, f"Erro ao navegar para o frame: {str(e_frame)[:50]}. Tentando continuar.\n")
            
            # Espera adicional para garantir carregamento completo
            time.sleep(3)
            
            # Implementação fiel do script JavaScript fornecido pelo usuário
            # para encontrar a última movimentação processual na tabela de movimentações
            
            # Aguardar um pouco mais antes de procurar a tabela - pode estar carregando dinamicamente
            time.sleep(5)  # Espera adicional para garantir o carregamento da página
            
            status_text_widget.insert(tk.END, f"Buscando tabela de movimentações para {process_number}...\n")
            
            # 1. Selecionar a tabela de movimentações com retry
            max_attempts = 3
            attempt = 0
            while attempt < max_attempts:
                try:
                    attempt += 1
                    status_text_widget.insert(tk.END, f"Tentativa {attempt} de localizar tabela de movimentações...\n")
                    
                    # Ajustando o timeout para 45 segundos conforme solicitado
                    tabela_movimentacoes_tbody = WebDriverWait(driver, 45).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "table.resultTable tbody"))
                    )
                    
                    if not tabela_movimentacoes_tbody:
                        if attempt < max_attempts:
                            status_text_widget.insert(tk.END, f"Tabela não encontrada. Tentando novamente ({attempt}/{max_attempts})...\n")
                            time.sleep(3)  # Espera entre tentativas
                            continue
                        else:
                            status_text_widget.insert(tk.END, f"Tabela de movimentações não encontrada após {max_attempts} tentativas.\n")
                            return "N/A", "TABELA DE MOVIMENTAÇÃO NÃO ENCONTRADA", executed_name
                    
                    status_text_widget.insert(tk.END, f"Tabela de movimentações encontrada! Extraindo dados...\n")
                    
                    # 2. Selecionar a primeira linha <tr> dentro do tbody (movimentação mais recente)
                    primeira_linha_mov = tabela_movimentacoes_tbody.find_element(By.TAG_NAME, "tr")
                    
                    if not primeira_linha_mov:
                        status_text_widget.insert(tk.END, f"Nenhuma linha de movimentação encontrada para {process_number}.\n")
                        return "N/A", "NENHUMA MOVIMENTAÇÃO ENCONTRADA", executed_name
                    
                    # Inicializar variáveis
                    date = "N/A"
                    description = "MOVIMENTAÇÃO NÃO ENCONTRADA"
                    
                    # 3. Extrair a data: está na terceira coluna (índice 2)
                    all_cells = primeira_linha_mov.find_elements(By.TAG_NAME, "td")
                    if all_cells and len(all_cells) > 2:
                        coluna_data = all_cells[2]
                        texto_data = coluna_data.text.strip()
                        status_text_widget.insert(tk.END, f"Texto da data encontrado: {texto_data}\n")
                        match_data = re.search(r'\d{2}\/\d{2}\/\d{4}', texto_data)
                        if match_data:
                            date = match_data.group(0)
                            status_text_widget.insert(tk.END, f"Data extraída: {date}\n")
                    
                    # 4. Extrair o evento/descrição da movimentação: está na quarta coluna (índice 3)
                    if all_cells and len(all_cells) > 3:
                        coluna_evento = all_cells[3]
                        evento_element = coluna_evento.find_element(By.TAG_NAME, "b")
                        if evento_element:
                            description = evento_element.text.strip()
                            status_text_widget.insert(tk.END, f"Descrição extraída: {description}\n")
                    
                    # Verifica se ambos os dados foram encontrados
                    if date == "N/A" or description == "MOVIMENTAÇÃO NÃO ENCONTRADA":
                        status_text_widget.insert(tk.END, f"Não foi possível extrair completamente os dados da movimentação.\n")
                    
                    # Se chegou até aqui, encontrou a tabela e tentou extrair os dados
                    break
                    
                except TimeoutException:
                    if attempt < max_attempts:
                        status_text_widget.insert(tk.END, f"Timeout ao buscar tabela. Tentativa {attempt}/{max_attempts}. Tentando novamente...\n")
                        # Tentar fazer scroll para baixo para ajudar a carregar a tabela
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(3)
                    else:
                        status_text_widget.insert(tk.END, f"Timeout final ao buscar tabela de movimentações após {max_attempts} tentativas.\n")
                        return "Erro PROJUDI (Timeout Tabela)", "Erro PROJUDI (Timeout Tabela)", executed_name
                
                except NoSuchElementException as nse:
                    status_text_widget.insert(tk.END, f"Elemento não encontrado ao extrair movimentação (tentativa {attempt}/{max_attempts}): {nse}\n")
                    if attempt < max_attempts:
                        time.sleep(3)  # Espera entre tentativas
                    else:
                        return "Erro PROJUDI (Elemento N/E)", "Erro PROJUDI (Elemento N/E)", executed_name
                
                except Exception as e:
                    status_text_widget.insert(tk.END, f"Erro ao extrair movimentação (tentativa {attempt}/{max_attempts}): {e}\n")
                    if attempt < max_attempts:
                        time.sleep(3)  # Espera entre tentativas
                    else:
                        return "Erro PROJUDI (Extração)", f"Erro PROJUDI: {str(e)[:50]}", executed_name
            
        except TimeoutException:
            status_text_widget.insert(tk.END, f"Erro PROJUDI (Timeout Mov) para {process_number}.\n")
            date = "Erro PROJUDI (Timeout Mov)"
            description = "Erro PROJUDI (Timeout Mov)"
        except NoSuchElementException:
            status_text_widget.insert(tk.END, f"Elemento da movimentação não encontrado para {process_number}.\n")
            date = "Erro PROJUDI (Elemento Mov N/E)"
            description = "Erro PROJUDI (Elemento Mov N/E)"
        except StaleElementReferenceException as sere: # Capturar erro de elemento obsoleto
            status_text_widget.insert(tk.END, f"Aviso (PROJUDI): Elemento obsoleto ao extrair movimentação para {process_number}: {sere}\n")
            date = "Erro PROJUDI (Elemento Obsoleto)"
            description = "Erro PROJUDI (Elemento Obsoleto)"
        except Exception as e_mov:
            status_text_widget.insert(tk.END, f"Erro inesperado ao processar movimentação de {process_number}: {e_mov}\n")
            date = "Erro PROJUDI (Movimentação)"
            description = "Erro PROJUDI (Movimentação)"
        
        return date, description, executed_name

    except TimeoutException as te:
        status_text_widget.insert(tk.END, f"Timeout geral ao interagir com PROJUDI para {process_number}: {te}\n")
        return "N/A", "Erro PROJUDI (Timeout Geral)", "N/A"
    except NoSuchElementException as nse:
        status_text_widget.insert(tk.END, f"Elemento não encontrado na página do PROJUDI para {process_number}: {nse}.\n")
        return "N/A", "Erro PROJUDI (Elemento Geral N/E)", "N/A"
    except WebDriverException as wde:
        status_text_widget.insert(tk.END, f"Erro do WebDriver ao consultar PROJUDI para {process_number}: {wde}\n")
        return "N/A", "Erro PROJUDI (WebDriver)", "N/A"
    except Exception as e:
        status_text_widget.insert(tk.END, f"Erro geral ao consultar PROJUDI para {process_number} com Selenium: {e}\n")
        return "N/A", "Erro PROJUDI (Geral)", "N/A"
    finally:
        if driver:
            try:
                driver.quit()
            except WebDriverException as e:
                status_text_widget.insert(tk.END, f"Aviso: Erro ao fechar o driver do Selenium para {process_number}: {e}\n")

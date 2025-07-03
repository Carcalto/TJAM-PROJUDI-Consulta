import logging
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
import re

from utils.constants import (
    STATUS_NAO_DISPONIVEL, STATUS_SEGREDO_JUSTICA, STATUS_MOVIMENTACAO_NAO_ENCONTRADA,
    PROJUDI_ERRO_CREDENCIAIS_INVALIDAS, PROJUDI_ERRO_USERMAINFRAME, PROJUDI_ERRO_PREENCHIMENTO,
    PROJUDI_PROCESS_NAO_ENCONTRADO, PROJUDI_PROCESS_NAO_LISTADO_POS_BUSCA,
    # PROJUDI_ERRO_TIMEOUT_TABELA, # Removido da importação global, será importado localmente
    PROJUDI_ERRO_NENHUMA_MOVIMENTACAO_ENCONTRADA,
    PROJUDI_ERRO_ELEMENTO_N_E, PROJUDI_ERRO_EXTRACAO, PROJUDI_ERRO_TIMEOUT_MOV,
    PROJUDI_ERRO_ELEMENTO_MOV_N_E, PROJUDI_ERRO_ELEMENTO_OBSOLETO, PROJUDI_ERRO_MOVIMENTACAO,
    PROJUDI_ERRO_TIMEOUT_GERAL, PROJUDI_ERRO_ELEMENTO_GERAL_N_E, PROJUDI_ERRO_WEBDRIVER,
    PROJUDI_ERRO_GERAL,
    SLEEP_LOGIN_PROJUDI, SLEEP_MENU_PROJUDI, SLEEP_FRAME_CHANGE_PROJUDI, SLEEP_FIELD_FILL_PROJUDI,
    SLEEP_SEARCH_PROJUDI, SLEEP_TABLE_RETRY, SLEEP_PAGE_LOAD, SLEEP_AFTER_PROJUDI_CONSULTA
)

logger = logging.getLogger(__name__)

class BasePage:
    def __init__(self, driver):
        self.driver = driver
        self.wait = WebDriverWait(driver, 30) # Tempo de espera padrão para elementos

    def _switch_to_main_frame(self):
        self.driver.switch_to.default_content()
        time.sleep(SLEEP_FRAME_CHANGE_PROJUDI)
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        try:
            self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.NAME, "userMainFrame")))
        except TimeoutException:
            logger.error(f"Timeout: Não foi possível focar no 'userMainFrame'.")
            raise TimeoutException(PROJUDI_ERRO_USERMAINFRAME)

class ProjudiLoginPage(BasePage):
    URL = "https://projudi.tjam.jus.br/projudi/"
    LOGIN_FIELD_XPATH = "//input[@id='login']"
    PASSWORD_FIELD_XPATH = "//input[@id='senha']"
    ENTER_BUTTON_XPATH = "//input[@id='btEntrar']"

    def goto(self):
        self.driver.get(self.URL)
        time.sleep(SLEEP_LOGIN_PROJUDI) # Espera para carregamento inicial

    def login(self, username, password):
        self.wait.until(EC.frame_to_be_available_and_switch_to_it((By.ID, "mainFrame")))
        
        login_field = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.LOGIN_FIELD_XPATH)))
        login_field.clear()
        login_field.send_keys(username)

        password_field = self.wait.until(EC.visibility_of_element_located((By.XPATH, self.PASSWORD_FIELD_XPATH)))
        password_field.clear()
        password_field.send_keys(password)

        enter_button = self.wait.until(EC.element_to_be_clickable((By.XPATH, self.ENTER_BUTTON_XPATH)))
        enter_button.click()
        time.sleep(SLEEP_LOGIN_PROJUDI) # Espera após o clique no login
        
        # Verificação de erro de login
        try:
            possible_error_messages = [
                "//font[@color='red']",
                "//*[contains(text(),'Usuário ou senha inválida')]",
                "//*[contains(text(),'Login inválido')]",
                "//*[contains(text(),'Problemas no login')]"
            ]
            for error_xpath in possible_error_messages:
                try:
                    error_element = self.driver.find_element(By.XPATH, error_xpath)
                    if error_element.is_displayed():
                        logger.warning(f"Possível erro de login no PROJUDI: {error_element.text}")
                        # Lança uma exceção para que a função chamadora possa tratar o erro de login
                        raise ValueError(PROJUDI_ERRO_CREDENCIAIS_INVALIDAS) 
                except NoSuchElementException:
                    continue
        except Exception as e_login_check:
            logger.warning(f"Aviso: Verificação de erro de login encontrou um problema: {e_login_check}")

class ProjudiMenuPage(BasePage):
    MENU_BUSCAS_ID = "Stm0p0i7eTX"
    PROCESSOS_1_GRAU_MENU_ITEM_ID = "Stm0p7i0e"

    def navigate_to_search(self):
        menu_buscas_element = self.wait.until(EC.visibility_of_element_located((By.ID, self.MENU_BUSCAS_ID)))
        ActionChains(self.driver).move_to_element(menu_buscas_element).perform()
        time.sleep(SLEEP_MENU_PROJUDI)

        processos_1_grau_element = self.wait.until(EC.element_to_be_clickable((By.ID, self.PROCESSOS_1_GRAU_MENU_ITEM_ID)))
        processos_1_grau_element.click()

class ProjudiSearchPage(BasePage):
    NUMERO_PROCESSO_FIELD_ID = "numeroProcesso"
    SEARCH_BUTTON_ID = "pesquisar"
    NO_RECORDS_XPATH = "//*[contains(text(), 'Nenhum registro encontrado')]"

    def search_process(self, process_number):
        self._switch_to_main_frame() # Garante que estamos no frame correto
        
        numero_processo_field = self.wait.until(EC.element_to_be_clickable((By.ID, self.NUMERO_PROCESSO_FIELD_ID)))
        numero_processo_field.clear()
        numero_processo_field.send_keys(process_number)
        
        # Recurso de preenchimento via JS se o send_keys falhar
        current_value = numero_processo_field.get_attribute('value')
        if current_value != process_number:
            self.driver.execute_script(f"arguments[0].value = '{process_number}';", numero_processo_field)
            current_value = numero_processo_field.get_attribute('value')
            if current_value != process_number:
                logger.error(f"Falha ao preencher 'numeroProcesso' para o processo {process_number}.")
                raise ValueError(PROJUDI_ERRO_PREENCHIMENTO)
        time.sleep(SLEEP_FIELD_FILL_PROJUDI)

        search_button = self.wait.until(EC.element_to_be_clickable((By.ID, self.SEARCH_BUTTON_ID)))
        try:
            search_button.click()
        except Exception: # Tenta clicar via JS se o click normal falhar
            self.driver.execute_script("arguments[0].click();", search_button)
        
        time.sleep(SLEEP_SEARCH_PROJUDI)

    def check_no_records_found(self):
        try:
            no_records_element = self.wait.until(
                EC.visibility_of_element_located((By.XPATH, self.NO_RECORDS_XPATH))
            )
            return no_records_element.is_displayed()
        except TimeoutException:
            return False

    def get_process_link_element(self, process_number):
        # Aguarda a presença do número do processo na tabela de resultados antes de tentar clicar
        try:
            process_link_td = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, f"//td[normalize-space()='{process_number}']"))
            )
            # Tenta encontrar um link 'a' dentro do TD, senão usa o próprio TD para clique
            try:
                process_link = process_link_td.find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                process_link = process_link_td
            return process_link
        except TimeoutException:
            logger.warning(f"PROJUDI: Processo {process_number} não encontrado na tabela de resultados após busca (Timeout esperando link do processo).")
            raise TimeoutException(PROJUDI_PROCESS_NAO_LISTADO_POS_BUSCA)

    def extract_process_info_from_row(self, linha_tr):
        """
        Extrai dados de uma linha de processo, incluindo nome do requerido/executado
        e se é segredo de justiça.
        """
        nome_executado = STATUS_NAO_DISPONIVEL
        segredo = False
        
        try:
            all_cells = linha_tr.find_elements(By.TAG_NAME, "td")
            
            for cell in all_cells:
                cell_text = cell.text.strip()
                if STATUS_SEGREDO_JUSTICA in cell_text:
                    segredo = True
                    break
            
            if segredo:
                return STATUS_NAO_DISPONIVEL, True
                    
            if len(all_cells) > 2: # Terceira coluna geralmente contém os dados das partes
                terceira_coluna = all_cells[2]
                
                table_forms = terceira_coluna.find_elements(By.CSS_SELECTOR, "table.form")
                if table_forms:
                    table_form = table_forms[0]
                    try:
                        requerido_font = table_form.find_element(By.XPATH, ".//font[contains(text(), 'Requerido:')]")
                        if requerido_font:
                            requerido_td = requerido_font.find_element(By.XPATH, "./..")
                            requerido_tr = requerido_td.find_element(By.XPATH, "./..")
                            td_with_name = requerido_tr.find_elements(By.TAG_NAME, "td")[1]
                            li_elements = td_with_name.find_elements(By.TAG_NAME, "li")
                            if li_elements and li_elements[0].text.strip():
                                nome_executado = li_elements[0].text.strip()
                                logger.info(f"Requerido encontrado: {nome_executado}")
                    except NoSuchElementException:
                        pass
            
            exec_labels = ["Requerido:", "Executado:", "Réu:", "Embargante:"]
            for i, cell in enumerate(all_cells):
                cell_text = cell.text.strip()
                for label in exec_labels:
                    if label.replace(":", "") in cell_text:
                        if (i + 1) < len(all_cells):
                            next_cell = all_cells[i + 1]
                            uls = next_cell.find_elements(By.TAG_NAME, "ul")
                            if uls:
                                lis = uls[0].find_elements(By.TAG_NAME, "li")
                                if lis and lis[0].text.strip():
                                    nome_executado = lis[0].text.strip()
                                    break
                        
                    if nome_executado != STATUS_NAO_DISPONIVEL:
                        break
            
            if nome_executado != STATUS_NAO_DISPONIVEL:
                nome_executado = re.sub(r'advogad[oa]:\s*.*', '', nome_executado, flags=re.IGNORECASE).strip()
                nome_executado = re.sub(r"^\(parte\s+\w+\):\s*", "", nome_executado, flags=re.IGNORECASE).strip()
                nome_executado = re.sub(r'\s+', ' ', nome_executado).strip()
            
            return nome_executado, segredo
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados da linha do processo: {e}")
            return STATUS_NAO_DISPONIVEL, False

class ProjudiProcessDetailPage(BasePage):
    MOV_TABLE_TBODY_CSS = "table.resultTable tbody"

    def extract_last_movement(self, executed_name):
        date = STATUS_NAO_DISPONIVEL
        description = STATUS_MOVIMENTACAO_NAO_ENCONTRADA
        
        self._switch_to_main_frame() # Garante que estamos no frame correto
        logger.info("Pronto para extrair dados da tabela.")
        time.sleep(SLEEP_PAGE_LOAD) # Espera adicional para garantir carregamento completo da página de detalhes

        logger.info("Buscando tabela de movimentações...")
        max_attempts = 3
        attempt = 0
        while attempt < max_attempts:
            try:
                attempt += 1
                logger.info(f"Tentativa {attempt} de localizar tabela de movimentações...")
                
                tabela_movimentacoes_tbody = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, self.MOV_TABLE_TBODY_CSS))
                )
                
                if not tabela_movimentacoes_tbody:
                    if attempt < max_attempts:
                        logger.info(f"Tabela não encontrada. Tentando novamente ({attempt}/{max_attempts})...")
                        time.sleep(SLEEP_TABLE_RETRY)
                        continue
                    else:
                        logger.error(f"Tabela de movimentações não encontrada após {max_attempts} tentativas.")
                        from utils.constants import PROJUDI_ERRO_TABELA_MOVIMENTACAO_N_E # Importado aqui para tentar resolver o falso positivo do Pylance
                        raise TimeoutException(PROJUDI_ERRO_TABELA_MOVIMENTACAO_N_E)
                
                logger.info("Tabela de movimentações encontrada! Extraindo dados...")
                
                primeira_linha_mov = tabela_movimentacoes_tbody.find_element(By.TAG_NAME, "tr")
                
                if not primeira_linha_mov:
                    logger.info("Nenhuma linha de movimentação encontrada.")
                    raise NoSuchElementException(PROJUDI_ERRO_NENHUMA_MOVIMENTACAO_ENCONTRADA)
                
                all_cells = primeira_linha_mov.find_elements(By.TAG_NAME, "td")
                if all_cells and len(all_cells) > 2:
                    coluna_data = all_cells[2]
                    texto_data = coluna_data.text.strip()
                    logger.info(f"Texto da data encontrado: {texto_data}")
                    match_data = re.search(r'\d{2}\/\d{2}\/\d{4}', texto_data)
                    if match_data:
                        date = match_data.group(0)
                        logger.info(f"Data extraída: {date}")
                
                if all_cells and len(all_cells) > 3:
                    coluna_evento = all_cells[3]
                    try:
                        evento_element = coluna_evento.find_element(By.TAG_NAME, "b")
                        description = evento_element.text.strip()
                        logger.info(f"Descrição extraída: {description}")
                    except NoSuchElementException:
                        # Se o elemento <b> não for encontrado, tenta pegar o texto da célula inteira
                        description = coluna_evento.text.strip()
                        logger.warning(f"Elemento <b> não encontrado; extraindo texto da célula: {description}")
                
                if date == STATUS_NAO_DISPONIVEL or description == STATUS_MOVIMENTACAO_NAO_ENCONTRADA:
                    logger.warning("Não foi possível extrair completamente os dados da movimentação.")
                
                break # Sai do loop while se encontrou e extraiu
                
            except TimeoutException as te:
                if attempt < max_attempts:
                    logger.warning(f"Timeout ao buscar tabela. Tentativa {attempt}/{max_attempts}. Tentando novamente...", exc_info=True)
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(SLEEP_TABLE_RETRY)
                else:
                    logger.error(f"Timeout final ao buscar tabela de movimentações após {max_attempts} tentativas.", exc_info=True)
                    from utils.constants import PROJUDI_ERRO_TIMEOUT_TABELA
                    raise TimeoutException(PROJUDI_ERRO_TIMEOUT_TABELA) from te
            
            except NoSuchElementException as nse:
                logger.error(f"Elemento não encontrado ao extrair movimentação (tentativa {attempt}/{max_attempts}): {nse}", exc_info=True)
                if attempt < max_attempts:
                    time.sleep(SLEEP_TABLE_RETRY)
                else:
                    raise NoSuchElementException(PROJUDI_ERRO_ELEMENTO_N_E) from nse
            
            except Exception as e:
                logger.error(f"Erro ao extrair movimentação (tentativa {attempt}/{max_attempts}): {e}", exc_info=True)
                if attempt < max_attempts:
                    time.sleep(SLEEP_TABLE_RETRY)
                else:
                    raise Exception(PROJUDI_ERRO_EXTRACAO) from e
        
        return date, description, executed_name

class ProjudiScraper:
    def __init__(self, driver):
        self.driver = driver
        self.login_page = ProjudiLoginPage(driver)
        self.menu_page = ProjudiMenuPage(driver)
        self.search_page = ProjudiSearchPage(driver)
        self.detail_page = ProjudiProcessDetailPage(driver)

    def get_movement(self, process_number, username, password):
        try:
            self.login_page.goto()
            self.login_page.login(username, password)
            self.menu_page.navigate_to_search()
            self.search_page.search_process(process_number)

            if self.search_page.check_no_records_found():
                return STATUS_NAO_DISPONIVEL, PROJUDI_PROCESS_NAO_ENCONTRADO, STATUS_NAO_DISPONIVEL

            process_link_element = self.search_page.get_process_link_element(process_number)
            
            # Extrair nome do executado e status de segredo de justiça antes de clicar no link
            process_row_element = process_link_element.find_element(By.XPATH, "./ancestor::tr[1]")
            executed_name, is_segredo_justica = self.search_page.extract_process_info_from_row(process_row_element)
            
            # Verificar se é segredo de justiça diretamente na página de resultados também
            if not is_segredo_justica:
                try:
                    segredo_justica_element = self.driver.find_element(By.XPATH, f"//*[contains(text(), '{STATUS_SEGREDO_JUSTICA}')]")
                    if segredo_justica_element and segredo_justica_element.is_displayed():
                        is_segredo_justica = True
                except NoSuchElementException:
                    pass

            if is_segredo_justica:
                logger.info(f"Processo {process_number} em {STATUS_SEGREDO_JUSTICA}.")
                return STATUS_NAO_DISPONIVEL, STATUS_SEGREDO_JUSTICA, executed_name

            process_link_element.click()
            time.sleep(SLEEP_AFTER_PROJUDI_CONSULTA) # Pausa após clicar no link do processo

            date, description, _ = self.detail_page.extract_last_movement(executed_name)
            return date, description, executed_name

        except ValueError as ve: # Captura erros de credenciais/preenchimento
            logger.error(f"Erro de validação no PROJUDI para {process_number}: {ve}")
            return STATUS_NAO_DISPONIVEL, str(ve), STATUS_NAO_DISPONIVEL
        except TimeoutException as te:
            logger.error(f"Timeout geral ao interagir com PROJUDI para {process_number}: {te}")
            return STATUS_NAO_DISPONIVEL, str(te), STATUS_NAO_DISPONIVEL
        except NoSuchElementException as nse:
            logger.error(f"Elemento não encontrado no site do PROJUDI para {process_number}: {nse}", exc_info=True)
            return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_ELEMENTO_GERAL_N_E, STATUS_NAO_DISPONIVEL
        except WebDriverException as wde:
            logger.error(f"Erro do WebDriver ao consultar PROJUDI para {process_number}: {wde}", exc_info=True)
            return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_WEBDRIVER, STATUS_NAO_DISPONIVEL
        except Exception as e:
            logger.error(f"Erro geral ao consultar PROJUDI para {process_number} com Selenium: {e}", exc_info=True)
            return STATUS_NAO_DISPONIVEL, PROJUDI_ERRO_GERAL, STATUS_NAO_DISPONIVEL
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                except WebDriverException as e:
                    logger.warning(f"Aviso: Erro ao fechar o driver do Selenium para {process_number}: {e}")

# Antiga função get_projudi_process_movement (será substituída pela classe ProjudiScraper)
"""
def get_projudi_process_movement(process_number, username, password):
    # ... código antigo ...
    pass
"""
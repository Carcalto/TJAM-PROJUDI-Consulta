import requests
from bs4 import BeautifulSoup
import re 
import logging 
from .projudi_orchestrator import get_projudi_process_movement
import time

# Importar constantes
from utils.constants import (
    STATUS_NAO_DISPONIVEL, STATUS_DATA_NAO_ENCONTRADA, STATUS_DESCRICAO_NAO_ENCONTRADA,
    SLEEP_AFTER_PROJUDI_CONSULTA
)

def get_tjam_process_movement(process_number, projudi_username, projudi_password):
    """
    Consulta a movimentação de um processo no portal SAJ (Sistema de Automação da Justiça) do TJAM.
    Tenta extrair a data e a descrição da última movimentação processual.

    Se o processo não for encontrado no SAJ, ou se houver uma indicação explícita de que
    o processo foi transferido para o sistema PROJUDI, ou ainda se não houver movimentações
    registradas no SAJ, a função automaticamente tentará consultar o mesmo número de processo
    no PROJUDI.

    Args:
        process_number (str): O número do processo a ser consultado.
        projudi_username (str): Nome de usuário para login no PROJUDI (caso necessário).
        projudi_password (str): Senha para login no PROJUDI (caso necessário).

    Returns:
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao, nome_executado).
               Em caso de erro ou se o processo não for encontrado em nenhum dos sistemas,
               pode retornar strings indicativas de erro ou "N/A" para os respectivos campos.
    """
    # Monta a URL de consulta do processo no portal SAJ do TJAM.
    url = f"https://consultasaj.tjam.jus.br/cpopg/show.do?&processo.numero={process_number}"
    
    date = STATUS_NAO_DISPONIVEL
    description = STATUS_DESCRICAO_NAO_ENCONTRADA
    executed_name = STATUS_NAO_DISPONIVEL
    should_fallback_to_projudi = False
    fallback_reason = ""

    try:
        # Realiza a requisição HTTP GET para a URL do processo.
        logging.info(f"Consultando SAJ/TJAM para o processo: {process_number}")
        response = requests.get(url)
        response.raise_for_status() # Levanta uma exceção para códigos de status HTTP 4xx ou 5xx.
        
        # Parseia o conteúdo HTML da página de resposta.
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Tenta encontrar a tabela principal de partes
        parts_table = soup.find('table', {'id': 'tablePartesPrincipais'})
        
        if parts_table:
            rows = parts_table.find_all('tr', class_='fundoClaro') 
            for row in rows:
                role_span = row.find('span', class_='tipoDeParticipacao')
                if role_span:
                    role_text = role_span.get_text(strip=True).lower()
                    
                    passive_party_terms = ["executado", "embargante", "requerido", "réu"]
                    active_party_terms = ["exequente", "embargado", "requerente"]
                    
                    is_passive_party = any(term in role_text for term in passive_party_terms)
                    is_active_party = any(term in role_text for term in active_party_terms)
                    
                    if is_passive_party and not is_active_party:
                        name_td = row.find('td', class_='nomeParteEAdvogado')
                        if name_td:
                            full_name_text = name_td.get_text(separator=' ', strip=True)
                            cleaned_name = re.sub(r'advogad[oa]:\s*.*', '', full_name_text, flags=re.IGNORECASE).strip()
                            executed_name = re.sub(r"^\(parte\s+\w+\):\s*", "", cleaned_name, flags=re.IGNORECASE).strip()
                            executed_name = re.sub(r'\s+', ' ', executed_name).strip() 
                            break 

        # Tenta encontrar a tabela de movimentações pelo ID 'tabelaTodasMovimentacoes'.
        movements_table = soup.find('table', {'id': 'tabelaTodasMovimentacoes'})
        if not movements_table:
            # Se não encontrar, tenta encontrar a tabela de últimas movimentações (alternativa).
            movements_table = soup.find('tbody', {'id': 'tabelaUltimasMovimentacoes'})

        if movements_table:
            rows = movements_table.find_all('tr', class_=['fundoClaro', 'fundoEscuro'])
            if rows:
                last_movement_row = rows[0]
                date_element = last_movement_row.find('td', class_='dataMovimentacao')
                description_element = last_movement_row.find('td', class_='descricaoMovimentacao')
                
                date = date_element.text.strip() if date_element else STATUS_DATA_NAO_ENCONTRADA
                raw_description = description_element.text.strip() if description_element else STATUS_DESCRICAO_NAO_ENCONTRADA
                description = re.sub(r'\s+', ' ', raw_description).strip()
                
                if "processo transferido para o projudi" in description.lower():
                    should_fallback_to_projudi = True
                    fallback_reason = "indica transferência"
                else:
                    # Se encontrou movimentação e não indica transferência, retorna os dados do SAJ
                    time.sleep(SLEEP_AFTER_PROJUDI_CONSULTA)
                    return date, description, executed_name
        
        # Se chegou aqui e não retornou, significa que a extração direta do SAJ não foi suficiente
        # e é preciso verificar as condições para fallback ao PROJUDI.
        if not should_fallback_to_projudi: # Só verifica se ainda não foi marcado para fallback
            page_content_text = soup.get_text().lower()
            if "processo transferido para o projudi" in page_content_text:
                should_fallback_to_projudi = True
                fallback_reason = "indica transferência"
            elif "não há movimentações" in page_content_text:
                should_fallback_to_projudi = True
                fallback_reason = "sem movimentações"
            elif not movements_table or not rows:
                should_fallback_to_projudi = True
                fallback_reason = "não foi possível extrair movimentações"
            else: # Caso em que movements_table e rows existem, mas o conteúdo não foi útil para um retorno SAJ
                should_fallback_to_projudi = True
                fallback_reason = "o conteúdo do SAJ não foi conclusivo"

    except requests.exceptions.RequestException as e:
        should_fallback_to_projudi = True
        fallback_reason = f"erro de conexão ({e})"
        logging.warning(f"Erro de conexão ao TJAM para o processo {process_number}: {e}. Tentando PROJUDI...", exc_info=True)
    except Exception as e:
        should_fallback_to_projudi = True
        fallback_reason = f"erro inesperado ({e})"
        logging.error(f"Erro ao processar o processo {process_number} no TJAM: {e}. Tentando PROJUDI...", exc_info=True)

    # Lógica de fallback para PROJUDI, executada apenas se should_fallback_to_projudi for True
    if should_fallback_to_projudi:
        logging.info(f"Processo {process_number} (TJAM) {fallback_reason}. Consultando PROJUDI...")
        projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password)
        time.sleep(SLEEP_AFTER_PROJUDI_CONSULTA)
        return projudi_date, projudi_description, projudi_executed_name
    else:
        # Este else só será alcançado se nenhum fallback foi acionado E não houve retorno antes.
        # Teoricamente, o retorno deveria ter acontecido dentro do if movements_table.
        # Isso atua como um `catch-all` para situações onde o SAJ não foi conclusivo e o fallback não foi disparado.
        logging.warning(f"Fluxo SAJ não conclusivo para {process_number} e sem fallback explícito acionado. Retornando dados SAJ parciais ou N/A.")
        return date, description, executed_name

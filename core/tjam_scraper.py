import requests
from bs4 import BeautifulSoup
import tkinter as tk # Para status_text_widget.insert, idealmente seria um callback ou logger
import re # Adicionado para limpeza de texto
from .projudi_scraper import get_projudi_process_movement # Importação correta

def get_tjam_process_movement(process_number, status_text_widget, projudi_username, projudi_password):
    """
    Consulta a movimentação de um processo no portal SAJ (Sistema de Automação da Justiça) do TJAM.
    Tenta extrair a data e a descrição da última movimentação processual.

    Se o processo não for encontrado no SAJ, ou se houver uma indicação explícita de que
    o processo foi transferido para o sistema PROJUDI, ou ainda se não houver movimentações
    registradas no SAJ, a função automaticamente tentará consultar o mesmo número de processo
    no PROJUDI.

    Args:
        process_number (str): O número do processo a ser consultado.
        status_text_widget: O widget de texto da UI onde as mensagens de status e logs são exibidas.
        projudi_username (str): Nome de usuário para login no PROJUDI (caso necessário).
        projudi_password (str): Senha para login no PROJUDI (caso necessário).

    Returns:
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao, nome_executado).
               Em caso de erro ou se o processo não for encontrado em nenhum dos sistemas,
               pode retornar strings indicativas de erro ou "N/A" para os respectivos campos.
    """
    # Monta a URL de consulta do processo no portal SAJ do TJAM.
    url = f"https://consultasaj.tjam.jus.br/cpopg/show.do?&processo.numero={process_number}"
    try:
        # Realiza a requisição HTTP GET para a URL do processo.
        response = requests.get(url)
        response.raise_for_status() # Levanta uma exceção para códigos de status HTTP 4xx ou 5xx.
        
        # Parseia o conteúdo HTML da página de resposta.
        soup = BeautifulSoup(response.text, 'html.parser')

        # Inicializa o nome do executado como N/A. Será preenchido se encontrado.
        executed_name = "N/A"

        # Tenta encontrar a tabela principal de partes
        parts_table = soup.find('table', {'id': 'tablePartesPrincipais'})

        if parts_table:
            # Encontra todas as linhas de partes
            rows = parts_table.find_all('tr', class_='fundoClaro') # O exemplo mostra fundoClaro

            for row in rows:
                # Procura pelo span que indica o tipo de participação (Exequente, Executado, etc.)
                role_span = row.find('span', class_='tipoDeParticipacao')
                if role_span:
                    role_text = role_span.get_text(strip=True).lower()
                    
                    # Define os termos que indicam a parte "executada" (Polo Passivo)
                    passive_party_terms = ["executado", "embargante", "requerido", "réu"]
                    # Define os termos que indicam a parte "exequente" (Polo Ativo), para exclusão
                    active_party_terms = ["exequente", "embargado", "requerente"]

                    # Verifica se o papel é de uma parte passiva e NÃO é de uma parte ativa
                    is_passive_party = any(term in role_text for term in passive_party_terms)
                    is_active_party = any(term in role_text for term in active_party_terms)

                    if is_passive_party and not is_active_party:
                        # O nome estará na próxima td com a classe 'nomeParteEAdvogado'
                        name_td = row.find('td', class_='nomeParteEAdvogado')
                        if name_td:
                            # Pega todo o texto dentro do elemento e limpa.
                            full_name_text = name_td.get_text(separator=' ', strip=True)
                            
                            # Remove a informação do advogado, se presente
                            cleaned_name = re.sub(r'advogad[oa]:\s*.*', '', full_name_text, flags=re.IGNORECASE).strip()
                            
                            # Remove qualquer texto tipo "(PARTE ATIVA):" ou "(PARTE PASSIVA):" no início
                            executed_name = re.sub(r"^\(parte\s+\w+\):\s*", "", cleaned_name, flags=re.IGNORECASE).strip()
                            
                            executed_name = re.sub(r'\s+', ' ', executed_name).strip() # Normaliza espaços
                            break # Encontrou o executado, pode parar de procurar

        # Tenta encontrar a tabela de movimentações pelo ID 'tabelaTodasMovimentacoes'.
        movements_table = soup.find('table', {'id': 'tabelaTodasMovimentacoes'})
        if not movements_table:
            # Se não encontrar, tenta encontrar a tabela de últimas movimentações (alternativa).
            movements_table = soup.find('tbody', {'id': 'tabelaUltimasMovimentacoes'})

        # Se uma tabela de movimentações for encontrada:
        if movements_table:
            # Encontra todas as linhas (<tr>) da tabela que correspondem a movimentações.
            rows = movements_table.find_all('tr', class_=['fundoClaro', 'fundoEscuro'])
            if rows:
                # A primeira linha (rows[0]) geralmente contém a movimentação mais recente.
                last_movement_row = rows[0]
                # Extrai a data da movimentação da célula com a classe 'dataMovimentacao'.
                date_element = last_movement_row.find('td', class_='dataMovimentacao')
                # Extrai a descrição da movimentação da célula com a classe 'descricaoMovimentacao'.
                description_element = last_movement_row.find('td', class_='descricaoMovimentacao')
                
                date = date_element.text.strip() if date_element else "Data não encontrada"
                raw_description = description_element.text.strip() if description_element else "Descrição não encontrada"
                # Limpa a descrição, removendo espaços extras e quebras de linha.
                description = re.sub(r'\s+', ' ', raw_description).strip()
                
                # Verifica se a descrição indica que o processo foi transferido para o PROJUDI.
                if "processo transferido para o projudi" in description.lower():
                    status_text_widget.insert(tk.END, f"Processo {process_number} (TJAM) indica transferência. Consultando PROJUDI...\n")
                    # Se transferido, chama a função para consultar no PROJUDI.
                    projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
                    return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI
                
                # Se não foi transferido, retorna a data e a descrição encontradas no TJAM, e o nome do executado.
                return date, description, executed_name

        # Se nenhuma tabela de movimentações foi encontrada ou se a tabela estava vazia,
        # analisa o texto completo da página em busca de indicações.
        page_content_text = soup.get_text().lower()

        # Verifica se o texto da página indica transferência para o PROJUDI.
        if "processo transferido para o projudi" in page_content_text:
            status_text_widget.insert(tk.END, f"Processo {process_number} (TJAM) indica transferência. Consultando PROJUDI...\n")
            projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
            return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI
        
        # Verifica se o texto da página indica que não há movimentações.
        if "não há movimentações" in page_content_text:
             status_text_widget.insert(tk.END, f"Processo {process_number} (TJAM) sem movimentações. Consultando PROJUDI...\n")
             # Mesmo sem movimentações no TJAM, pode haver no PROJUDI (ex: processos mais antigos migrados).
             projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
             return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI

        # Se nenhuma das condições anteriores foi atendida (sem tabela, sem texto indicativo claro),
        # por precaução, tenta consultar no PROJUDI.
        status_text_widget.insert(tk.END, f"Não foi possível extrair movimentações do TJAM para {process_number}. Consultando PROJUDI...\n")
        projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
        return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI

    except requests.exceptions.RequestException as e:
        # Em caso de erro de conexão com o servidor do TJAM (ex: timeout, DNS),
        # informa o erro e tenta consultar diretamente no PROJUDI.
        status_text_widget.insert(tk.END, f"Erro de conexão ao TJAM para o processo {process_number}: {e}. Tentando PROJUDI...\n")
        projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
        return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI
    except Exception as e:
        # Para qualquer outro erro inesperado durante o processamento da página do TJAM,
        # informa o erro e tenta consultar no PROJUDI como fallback.
        status_text_widget.insert(tk.END, f"Erro ao processar o processo {process_number} no TJAM: {e}. Tentando PROJUDI...\n")
        projudi_date, projudi_description, projudi_executed_name = get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
        return projudi_date, projudi_description, projudi_executed_name # Retorna os dados do PROJUDI

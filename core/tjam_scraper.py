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
        tuple: Uma tupla contendo (data_da_movimentacao, descricao_da_movimentacao).
               Em caso de erro ou se o processo não for encontrado em nenhum dos sistemas,
               pode retornar strings indicativas de erro ou "N/A".
    """
    # Monta a URL de consulta do processo no portal SAJ do TJAM.
    url = f"https://consultasaj.tjam.jus.br/cpopg/show.do?&processo.numero={process_number}"
    try:
        # Realiza a requisição HTTP GET para a URL do processo.
        response = requests.get(url)
        response.raise_for_status() # Levanta uma exceção para códigos de status HTTP 4xx ou 5xx.
        
        # Parseia o conteúdo HTML da página de resposta.
        soup = BeautifulSoup(response.text, 'html.parser')

        # Verifica se existe o pop-up de "SENHA DO PROCESSO"
        # O título do pop-up é "SENHA DO PROCESSO" e contém o texto "Atendendo a resolução 121 do CNJ."
        # Podemos procurar por um elemento que contenha um desses textos.
        # Um seletor comum para o título de dialogs/modals pode ser um h1, h2, h3, ou um span com uma classe específica.
        # Vamos procurar por um texto mais genérico que provavelmente estará presente.
        # A imagem mostra "SENHA DO PROCESSO" como um título destacado.
        # E o texto "Atendendo a resolução 121 do CNJ."
        # Vamos procurar por um elemento que contenha "SENHA DO PROCESSO" ou "resolução 121 do CNJ"
        
        # Tentativa de encontrar o modal de senha. O modal pode ter um ID ou classe específica,
        # mas como não temos o HTML exato, vamos procurar por texto característico.
        # O texto "SENHA DO PROCESSO" parece ser um bom indicador.
        # Outro texto é "Atendendo a resolução 121 do CNJ."
        # E também "Se for uma parte ou interessado, digite a senha do processo"
        
        # Vamos procurar por um elemento que contenha o texto "SENHA DO PROCESSO"
        # ou "Digite a senha do processo" que é bem específico do modal.
        # Usar soup.find(text=re.compile(...)) pode ser útil.
        
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
                    return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
                
                # Se não foi transferido, retorna a data e a descrição encontradas no TJAM.
                return date, description

        # Se nenhuma tabela de movimentações foi encontrada ou se a tabela estava vazia,
        # analisa o texto completo da página em busca de indicações.
        page_content_text = soup.get_text().lower()

        # Verifica se o texto da página indica transferência para o PROJUDI.
        if "processo transferido para o projudi" in page_content_text:
            status_text_widget.insert(tk.END, f"Processo {process_number} (TJAM) indica transferência. Consultando PROJUDI...\n")
            return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
        
        # Verifica se o texto da página indica que não há movimentações.
        if "não há movimentações" in page_content_text:
             status_text_widget.insert(tk.END, f"Processo {process_number} (TJAM) sem movimentações. Consultando PROJUDI...\n")
             # Mesmo sem movimentações no TJAM, pode haver no PROJUDI (ex: processos mais antigos migrados).
             return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)

        # Se nenhuma das condições anteriores foi atendida (sem tabela, sem texto indicativo claro),
        # por precaução, tenta consultar no PROJUDI.
        status_text_widget.insert(tk.END, f"Não foi possível extrair movimentações do TJAM para {process_number}. Consultando PROJUDI...\n")
        return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)

    except requests.exceptions.RequestException as e:
        # Em caso de erro de conexão com o servidor do TJAM (ex: timeout, DNS),
        # informa o erro e tenta consultar diretamente no PROJUDI.
        status_text_widget.insert(tk.END, f"Erro de conexão ao TJAM para o processo {process_number}: {e}. Tentando PROJUDI...\n")
        return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)
    except Exception as e:
        # Para qualquer outro erro inesperado durante o processamento da página do TJAM,
        # informa o erro e tenta consultar no PROJUDI como fallback.
        status_text_widget.insert(tk.END, f"Erro ao processar o processo {process_number} no TJAM: {e}. Tentando PROJUDI...\n")
        return get_projudi_process_movement(process_number, projudi_username, projudi_password, status_text_widget)

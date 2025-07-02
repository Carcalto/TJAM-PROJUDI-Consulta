# Este módulo lida com todas as interações relacionadas a arquivos Excel,
# como ler números de processo de uma planilha e salvar os resultados da consulta
# em uma nova planilha.
import pandas as pd # Biblioteca para manipulação e análise de dados, usada para ler/escrever Excel.
from tkinter import filedialog # Para caixas de diálogo de seleção/salvamento de arquivo. MessageBox será substituído por logging.
import logging # Adicionar import de logging

def is_valid_process_number(process_number):
    """
    Valida se um número de processo tem exatamente 20 caracteres numéricos após remover caracteres especiais.
    
    Args:
        process_number (str): O número do processo a ser validado.
        
    Returns:
        bool: True se o número for válido, False caso contrário.
    """
    # Remove caracteres não numéricos (pontos, hífens, espaços, etc.)
    digits_only = ''.join(filter(str.isdigit, str(process_number)))
    
    # Verifica se restaram exatamente 20 dígitos
    return len(digits_only) == 20

def read_process_numbers_from_excel(file_path):
    """
    Lê os números dos processos de um arquivo Excel.
    Valida cada número para garantir que tem 20 caracteres numéricos.
    
    Returns:
        tuple: (valid_numbers, invalid_numbers) onde:
               - valid_numbers é uma lista de números de processo válidos
               - invalid_numbers é uma lista de números de processo inválidos
    """
    try:
        df = pd.read_excel(file_path)
        
        # Identificar a coluna correta
        process_column = None
        if "PROCESSO" in df.columns:
            process_column = "PROCESSO"
        elif "processo" in df.columns:
            process_column = "processo"
        else:
            logging.error("O arquivo Excel deve conter uma coluna chamada 'PROCESSO' ou 'processo'.")
            return None, None
        
        # Converter todos os números para string e validar
        all_numbers = df[process_column].astype(str).tolist()
        valid_numbers = []
        invalid_numbers = []
        
        for num in all_numbers:
            if is_valid_process_number(num):
                valid_numbers.append(num)
            else:
                invalid_numbers.append(num)
                
        if invalid_numbers:
            logging.warning(f"Foram encontrados {len(invalid_numbers)} números de processo inválidos. "
                                   f"Eles serão incluídos no resultado final como 'NÚMERO DE PROCESSO INVÁLIDO'.")
                
        return valid_numbers, invalid_numbers
    except Exception as e:
        logging.error(f"Ocorreu um erro ao ler o arquivo Excel: {e}", exc_info=True)
        return None, None
 
def save_results_to_excel(results_list, default_filename="resultados_consulta.xlsx"):
    """
    Salva uma lista de dicionários (resultados) em um arquivo Excel.
    Retorna o caminho do arquivo salvo ou None se o salvamento for cancelado.
    """
    if not results_list: # Se a lista de resultados estiver vazia.
        logging.info("Não há resultados para salvar.")
        return None
 
    # Cria um DataFrame do Pandas a partir da lista de dicionários.
    output_df = pd.DataFrame(results_list)
    
    # Abre uma caixa de diálogo para o usuário escolher onde salvar o arquivo Excel.
    output_file_path = filedialog.asksaveasfilename(
        defaultextension=".xlsx", # Extensão padrão do arquivo.
        initialfile=default_filename, # Nome de arquivo sugerido.
        filetypes=[("Excel files", "*.xlsx")] # Filtro de tipo de arquivo.
    )
    
    if output_file_path: # Se o usuário selecionou um local e nome de arquivo.
        try:
            # Salva o DataFrame no arquivo Excel especificado, sem incluir o índice do DataFrame.
            output_df.to_excel(output_file_path, index=False)
            logging.info(f"Resultados salvos em:\n{output_file_path}")
            return output_file_path # Retorna o caminho do arquivo salvo.
        except Exception as e:
            logging.error(f"Não foi possível salvar o arquivo Excel: %s", e, exc_info=True)
            return None # Retorna None em caso de erro ao salvar.
    else:
        # Se o usuário cancelou a caixa de diálogo de salvamento.
        logging.info("Salvamento do arquivo de resultados cancelado.")
        return None

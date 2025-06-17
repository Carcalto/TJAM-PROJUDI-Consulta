# Este módulo lida com todas as interações relacionadas a arquivos Excel,
# como ler números de processo de uma planilha e salvar os resultados da consulta
# em uma nova planilha.
import pandas as pd # Biblioteca para manipulação e análise de dados, usada para ler/escrever Excel.
from tkinter import filedialog, messagebox # Para caixas de diálogo de seleção/salvamento de arquivo e mensagens.

def read_process_numbers_from_excel(file_path):
    """
    Lê os números dos processos de um arquivo Excel.
    Retorna uma lista de números de processo ou None em caso de erro.
    """
    try:
        df = pd.read_excel(file_path)
        if "PROCESSO" in df.columns:
            return df["PROCESSO"].astype(str).tolist()
        elif "processo" in df.columns:
            return df["processo"].astype(str).tolist()
        else:
            messagebox.showerror("Erro de Leitura", "O arquivo Excel deve conter uma coluna chamada 'PROCESSO' ou 'processo'.")
            return None
    except Exception as e:
        messagebox.showerror("Erro de Leitura", f"Ocorreu um erro ao ler o arquivo Excel: {e}")
        return None

def save_results_to_excel(results_list, default_filename="resultados_consulta.xlsx"):
    """
    Salva uma lista de dicionários (resultados) em um arquivo Excel.
    Retorna o caminho do arquivo salvo ou None se o salvamento for cancelado.
    """
    if not results_list: # Se a lista de resultados estiver vazia.
        messagebox.showinfo("Sem Resultados", "Não há resultados para salvar.")
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
            messagebox.showinfo("Concluído", f"Resultados salvos em:\n{output_file_path}")
            return output_file_path # Retorna o caminho do arquivo salvo.
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo Excel: {e}")
            return None # Retorna None em caso de erro ao salvar.
    else:
        # Se o usuário cancelou a caixa de diálogo de salvamento.
        return None

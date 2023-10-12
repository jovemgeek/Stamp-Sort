import os
import shutil
import re
import threading
import time
from datetime import datetime
from tkinter import ttk
from google.cloud import vision
from google.oauth2 import service_account
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Progressbar
import tkinter.messagebox as messagebox
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk
from ttkthemes import ThemedTk
entry_credenciais = None
imagens_processadas = 0
agp_nao_encontrada = 0
total_imagens = 0
path = "path"


# Local absoluto do arquivo config.txt
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")

# Configurar o cliente Vision API
credenciais = os.path.join(path, "cred.json")
creds = service_account.Credentials.from_service_account_file(credenciais)
client = vision.ImageAnnotatorClient(credentials=creds)

# Funções
def cancelar_processamento():
    global cancelar
    cancelar = True
    messagebox.showinfo("Cancelar", "O processamento será cancelado após a conclusão da imagem atual.")

def selecionar_arquivo_credenciais():
    global credenciais
    credenciais = filedialog.askopenfilename()
    entry_credenciais.delete(0, tk.END)
    entry_credenciais.insert(0, credenciais)

def mostrar_sobre():
    messagebox.showinfo("Sobre", "Organizador de Imagens por AGP\nVersão 2.0 de 21/08/2023\nDesenvolvido por Gabriel Ribeiro\nUtilizando Google Cloud Vision API")

# Funções para salvar e carregar os caminhos das pastas
def salvar_caminhos(entrada, saida):
    with open(config_path, "w") as f:
        f.write(entrada + "\n")
        f.write(saida)

def carregar_caminhos():
    if os.path.exists(config_path):
        with open(config_path, "r") as f:
            linhas = f.readlines()
            if len(linhas) >= 2:
                return linhas[0].strip(), linhas[1].strip()
    return None, None

def selecionar_pasta_entrada():
    dir_entrada = filedialog.askdirectory()
    entry_pasta_entrada.delete(0, tk.END)
    entry_pasta_entrada.insert(0, dir_entrada)
    salvar_caminhos(dir_entrada, entry_pasta_saida.get())

def selecionar_pasta_saida():
    dir_saida = filedialog.askdirectory()
    entry_pasta_saida.delete(0, tk.END)
    entry_pasta_saida.insert(0, dir_saida)
    salvar_caminhos(entry_pasta_entrada.get(), dir_saida)


def extrair_agp(imagem_path):
    with open(imagem_path, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    texts = response.text_annotations

    agp = None
    agp_pattern = re.compile(r'(AGP)[\s]?(\d{4})[\s]?([AB]?)', re.IGNORECASE)  # Adicione [\s]? para lidar com espaços
    for text in texts:
        match = agp_pattern.search(text.description)
        if match:
            inspecao = match.group(3) if match.group(3) else 'A'  # Se a letra A ou B não for encontrada, use 'A' como padrão
            ano = "22" if int(match.group(2)) < 1100 else "23"
            agp = f"{match.group(1)}-{match.group(2)}{inspecao}{ano}".upper()  # Inclua a letra e o ano '22' ou '23' no nome da pasta
            break
    return agp

def determinar_pasta_agp(agp_numero):
    intervalo_inicio = (agp_numero // 1000) * 1000
    intervalo_fim = intervalo_inicio + 999
    return f"AGP-{intervalo_inicio} ATÉ AGP-{intervalo_fim}"

def criar_diretorio_agp(agp, dir_saida):
    agp_numero = int(agp.split('-')[1][:4])
    pasta_agp = determinar_pasta_agp(agp_numero)
    dir_agp = os.path.join(dir_saida, pasta_agp, agp)
    if not os.path.exists(dir_agp):
        os.makedirs(dir_agp, exist_ok=True)  # Adicione o argumento exist_ok=True aqui
    return dir_agp


def atualizar_progresso(progresso_atual, total_imagens, status):
    def update_progress():
        percentual = progresso_atual / total_imagens * 100
        barra_progresso['value'] = percentual
        percentual_var.set(f"{percentual:.1f}%")
        status_var.set(status)

    root.after(0, update_progress)  # Schedule the update_progress function to run in the main thread

def atualizar_info(force_update=False):
    lbl_imagens_processadas.config(text=f"Imagens processadas: {imagens_processadas}")
    lbl_agp_nao_encontrada.config(text=f"AGP não encontrada: {agp_nao_encontrada}")
    # Cálculo do tempo restante estimado
    progresso_atual = imagens_processadas + agp_nao_encontrada
    if progresso_atual == 0:
        lbl_tempo_restante.config(text=f"Tempo restante estimado: 00h 00m")
    else:
        tempo_decorrido = time.time() - tempo_inicio
        tempo_medio_por_imagem = tempo_decorrido / progresso_atual
        tempo_restante = tempo_medio_por_imagem * (total_imagens - progresso_atual)
        horas_restantes, resto = divmod(tempo_restante, 3600)
        minutos_restantes, _ = divmod(resto, 60)
        lbl_tempo_restante.config(text=f"Tempo restante estimado: {int(horas_restantes)}h {int(minutos_restantes)}m")
        if force_update:
            lbl_imagens_processadas.update_idletasks()
            lbl_agp_nao_encontrada.update_idletasks()
            lbl_tempo_restante.update_idletasks()

def criar_diretorio_agp_nao_encontrada(dir_saida):
    dir_agp_nao_encontrada = os.path.join(dir_saida, "AGP Nao Encontrada")
    if not os.path.exists(dir_agp_nao_encontrada):
        os.makedirs(dir_agp_nao_encontrada, exist_ok=True)  # Adicione o argumento exist_ok=True aqui
    return dir_agp_nao_encontrada

def copiar_imagem(imagem_path, destino):
    shutil.copy2(imagem_path, os.path.join(destino, os.path.basename(imagem_path)))

def processar_imagens():
    global total_imagens # Adicione esta linha
    dir_entrada = entry_pasta_entrada.get()
    dir_saida = entry_pasta_saida.get()
    total_imagens = contar_imagens(dir_entrada)

    if total_imagens == 0:
        messagebox.showerror("Erro", "Não há imagens na pasta de entrada.")
        return

    threading.Thread(target=processar_imagens_thread, args=(dir_entrada, dir_saida, total_imagens)).start()


def atualizar_miniatura(imagem_path):
    """Atualiza a miniatura da imagem na interface gráfica."""
    with Image.open(imagem_path) as img:
        img.thumbnail((150, 150))  # Redimensiona a imagem para ter no máximo 150x150 pixels
        tk_img = ImageTk.PhotoImage(img)
        lbl_miniatura.config(image=tk_img)
        lbl_miniatura.image = tk_img  # Mantenha uma referência para evitar que a imagem seja coletada como lixo


def comprimir_imagem(caminho_imagem, qualidade=25):
    """
    Comprime a imagem para reduzir o tamanho do arquivo.
    
    :param caminho_imagem: Caminho da imagem a ser comprimida.
    :param qualidade: Qualidade da compressão (0 a 100). Valor padrão é 85.
    """
    with Image.open(caminho_imagem) as img:
        img.save(caminho_imagem, "JPEG", optimize=True, quality=qualidade)

def processar_imagem(imagem_path, dir_saida, dir_agp_nao_encontrada, total_imagens):
    atualizar_miniatura(imagem_path)
    comprimir_imagem(imagem_path)    
    agp = extrair_agp(imagem_path)
    if agp:
        dir_agp = criar_diretorio_agp(agp, dir_saida)
        copiar_imagem(imagem_path, dir_agp)
        return "encontrada"
    else:
        copiar_imagem(imagem_path, dir_agp_nao_encontrada)
        return "nao_encontrada"


def contar_imagens(dir_entrada):
    total_imagens = 0
    for root, _, arquivos in os.walk(dir_entrada):
        for arquivo in arquivos:
            if arquivo.lower().endswith((".png", ".jpg", ".jpeg")):
                total_imagens += 1
    return total_imagens


def criar_pasta_data_hora_backup():
    """Cria uma pasta com a data e hora atual no diretório de backup especificado."""
    backup_path = "G:\\Meu Drive\\REDE AMILGAS\\Nova pasta\\Luiz e Gabriel\\backup de fotos processadas"
    
    # Formatar a data e hora atual
    data_hora_atual = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    nova_pasta = os.path.join(backup_path, data_hora_atual)
    
    # Criar a pasta
    if not os.path.exists(nova_pasta):
        os.makedirs(nova_pasta)
    
    return nova_pasta

def processar_imagens_thread(dir_entrada, dir_saida, total_imagens):
    global cancelar, tempo_inicio, imagens_processadas, agp_nao_encontrada
    cancelar = False

    if not os.path.exists(dir_entrada):
        messagebox.showerror("Erro", "Selecione uma pasta de entrada válida.")
        return
    if not os.path.exists(dir_saida):
        os.makedirs(dir_saida)

    # Criar a pasta com data e hora
    pasta_data_hora = criar_pasta_data_hora_backup()

    dir_agp_nao_encontrada = criar_diretorio_agp_nao_encontrada(dir_saida)
    log(f"Iniciando o processamento das imagens... Total de imagens: {total_imagens}")

    tempo_inicio = time.time()
    progresso_atual = 0
    imagens_paths = []
    for root, _, arquivos in os.walk(dir_entrada):  # Percorre recursivamente as subpastas e arquivos
        if cancelar:
            break
        for arquivo in arquivos:
            if cancelar:
                break
            if arquivo.lower().endswith((".png", ".jpg", ".jpeg")):
                imagem_path = os.path.join(root, arquivo)
                imagens_paths.append(imagem_path)

    # Mover todas as imagens para a pasta criada
    for imagem_path in imagens_paths:
        shutil.move(imagem_path, pasta_data_hora)

    # Atualizar a lista de imagens_paths para refletir a nova localização
    imagens_paths = [os.path.join(pasta_data_hora, os.path.basename(imagem_path)) for imagem_path in imagens_paths]

    imagens_processadas = 0  # Inicialize imagens_processadas aqui
    agp_nao_encontrada = 0   # Inicialize agp_nao_encontrada aqui

    try:
        with ThreadPoolExecutor() as executor:
            futures = [executor.submit(processar_imagem, imagem_path, dir_saida, dir_agp_nao_encontrada, total_imagens) for imagem_path in imagens_paths]
            for index, future in enumerate(concurrent.futures.as_completed(futures)):
                result = future.result()  # Obtenha o resultado da função processar_imagem
                if result == "encontrada":
                    imagens_processadas += 1
                elif result == "nao_encontrada":
                    agp_nao_encontrada += 1

                progresso_atual += 1
                log(f"Processando imagem {progresso_atual} de {total_imagens}")
                atualizar_progresso(progresso_atual, total_imagens, f"Processando imagem {progresso_atual} de {total_imagens}")
                atualizar_info(force_update=True)
    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro durante o processamento: {str(e)}")
        return

    if cancelar:
        atualizar_progresso(0, total_imagens, f"Processamento cancelado.")
    else:
        tempo_final = time.time()
        tempo_decorrido = tempo_final - tempo_inicio
        horas_decorridas, resto = divmod(tempo_decorrido, 3600)
        minutos_decorridos, _ = divmod(resto, 60)
        atualizar_progresso(total_imagens, total_imagens, f"Concluído em {int(horas_decorridas)}h {int(minutos_decorridos)}m {tempo_decorrido % 60:.2f}s")

    # Adicionando a mensagem após a conclusão
    messagebox.showinfo("Concluído", "O processamento das imagens foi concluído com sucesso! Clique OK para continuar.")
    
def selecionar_arquivo_credenciais():
    global entry_credenciais
    credenciais = filedialog.askopenfilename()
    entry_credenciais.delete(0, tk.END)
    entry_credenciais.insert(0, credenciais)

def mostrar_sobre():
    messagebox.showinfo("Sobre", "Organizador de Imagens por AGP\nVersão 1.0\nDesenvolvido por Gabriel Ribeiro\nPara mais informações: gabrielrszj@icloud.com")

# Janela principal
root = ThemedTk(theme="scidgreen")
root.title("Organizador de Imagens por AGP By Gabriel Ribeiro")
root.geometry("850x430")  # Ajustado para acomodar a miniatura ao lado
root.iconbitmap('pngegg.ico')

# Menu
menu = tk.Menu(root)
root.config(menu=menu)
menu_sobre = tk.Menu(menu)
menu.add_cascade(label="Sobre", menu=menu_sobre)
menu_sobre.add_command(label="Informações", command=mostrar_sobre)

# Campos de seleção de pasta
entrada_frame = tk.Frame(root)
entrada_frame.grid(row=0, columnspan=2, padx=10, pady=10)
lbl_pasta_entrada = tk.Label(entrada_frame, text="Pasta de entrada:")
lbl_pasta_entrada.pack(side=tk.LEFT)
entry_pasta_entrada = tk.Entry(entrada_frame,width=40)
entry_pasta_entrada.pack(side=tk.LEFT)
btn_selecionar_pasta_entrada = ttk.Button(entrada_frame, text="Selecionar", command=selecionar_pasta_entrada)
btn_selecionar_pasta_entrada.pack(side=tk.LEFT)

saida_frame = tk.Frame(root)
saida_frame.grid(row=1, columnspan=2, padx=10, pady=10)
lbl_pasta_saida = tk.Label(saida_frame, text="Pasta de saída:")
lbl_pasta_saida.pack(side=tk.LEFT)
entry_pasta_saida = tk.Entry(saida_frame, width=40)
entry_pasta_saida.pack(side=tk.LEFT)
btn_selecionar_pasta_saida = ttk.Button(saida_frame, text="Selecionar", command=selecionar_pasta_saida)
btn_selecionar_pasta_saida.pack(side=tk.LEFT)

# Botões de processamento e cancelamento
btn_frame = tk.Frame(root)  # Frame adicional para agrupar os botões
btn_frame.grid(row=4, columnspan=2, padx=10, pady=10)

btn_processar = ttk.Button(btn_frame, text="Processar imagens", command=processar_imagens)
btn_processar.pack(side=tk.LEFT, padx=5)  # Espaço entre os botões

btn_cancelar = ttk.Button(btn_frame, text="Cancelar processamento", command=cancelar_processamento)
btn_cancelar.pack(side=tk.LEFT, padx=5)  # Espaço entre os botões

# Carregar os caminhos ao iniciar o programa
entrada_salva, saida_salva = carregar_caminhos()
if entrada_salva:
    entry_pasta_entrada.insert(0, entrada_salva)
if saida_salva:
    entry_pasta_saida.insert(0, saida_salva)

# Barra de progresso e rótulos
progresso_frame = tk.Frame(root)
progresso_frame.grid(row=5, columnspan=2, padx=10, pady=10)
percentual_var = tk.StringVar()
percentual_var.set("0.0%")
percentual_label = tk.Label(progresso_frame, textvariable=percentual_var)
percentual_label.pack(side=tk.LEFT)

barra_progresso = ttk.Progressbar(progresso_frame, orient=tk.HORIZONTAL, length=300, mode='determinate')
barra_progresso.pack(side=tk.LEFT)

status_var = tk.StringVar()
status_var.set("")
status_label = tk.Label(progresso_frame, textvariable=status_var)
status_label.pack(side=tk.LEFT)

# Rótulos de informações
info_frame = tk.Frame(root)
info_frame.grid(row=7, columnspan=2, padx=10, pady=10)

lbl_imagens_processadas = tk.Label(info_frame, text=f"Imagens processadas: {imagens_processadas}")
lbl_imagens_processadas.grid(row=0, column=0, padx=10, pady=10)

lbl_agp_nao_encontrada = tk.Label(info_frame, text=f"AGP não encontrada: {agp_nao_encontrada}")
lbl_agp_nao_encontrada.grid(row=0, column=1, padx=10, pady=10)

lbl_tempo_restante = tk.Label(info_frame, text=f"Tempo restante estimado: 00h 00m")
lbl_tempo_restante.grid(row=0, column=2, padx=10, pady=10)

atualizar_info(force_update=True)

# Miniatura
miniatura_frame = tk.Frame(root)
miniatura_frame.grid(row=6, column=1, padx=10, pady=10, sticky='e')  # Posicionado ao lado do campo de log
lbl_miniatura = tk.Label(miniatura_frame)
lbl_miniatura.pack()

# Campo de log
log_frame = tk.Frame(root)
log_frame.grid(row=6, column=0, padx=10, pady=10, sticky='w')  # Organizado em sua própria frame
log_text = tk.Text(log_frame, wrap=tk.WORD, height=10, width=80)
log_text.pack()
log_text.config(state=tk.DISABLED)  # Inicialmente, desative a edição

def log(message):
    def update_log():
        log_text.config(state=tk.NORMAL)  # Ative a edição temporariamente
        log_text.insert(tk.END, message + "\n")
        log_text.see(tk.END)  # Role até o final do texto
        log_text.config(state=tk.DISABLED)  # Desative a edição novamente

    root.after(0, update_log)  # Schedule the update_log function to run in the main thread

    
def main():
    root.mainloop()

if __name__ == "__main__":
    main()

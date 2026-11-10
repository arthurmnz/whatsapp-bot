import wakeonlan

# Substitua pelo Endereço Físico (MAC Address) do seu Windows
MAC_ADDRESS = "10-FF-E0-01-AA-D1"

def ligar_pc(mac):
    try:
        print(f"Enviando Magic Packet para {mac}...")

        # O send_magic_packet envia o pacote de broadcast para a rede (255.255.255.255)
        # O PC com este MAC específico vai reconhecer e ligar
        wakeonlan.wake(mac)

        print("Pacote enviado com sucesso! O Windows deve ligar em alguns segundos.")
    except Exception as e:
        print(f"Erro ao enviar o pacote: {e}")

ligar_pc(MAC_ADDRESS)

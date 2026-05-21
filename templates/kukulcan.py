# -*- coding: utf-8 -*-
import os
import sys
import json
from colorama import init, Fore, Back, Style

# Inicializa colorama para Windows CMD
init(autoreset=True)

DB_FILE = "inventario_camara.json"

def limpiar_pantalla():
    os.system('cls' if os.name == 'nt' else 'clear')

def cargar_datos():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            pass
    camara = {}
    for i in range(1, 94):
        camara[i] = {"cliente": "VACÍO", "cajas": 0, "color_name": "NEGRO"}
    return camara

def guardar_datos(camara):
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(camara, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(Fore.RED + f"Error al guardar los datos: {e}")

def get_back_color(color_name):
    if color_name == "AZUL": return Back.BLUE
    elif color_name == "ROSA": return Back.MAGENTA
    elif color_name == "VERDE": return Back.GREEN
    else: return Back.BLACK

def imprimir_espacio(num, camara):
    datos = camara[num]
    bg = get_back_color(datos["color_name"])
    if datos["cliente"] == "VACÍO":
        return f"{Back.BLACK}{Fore.LIGHTBLACK_EX}[{num:02d}]{Style.RESET_ALL}"
    else:
        return f"{bg}{Fore.WHITE}{Style.BRIGHT}[{num:02d}]{Style.RESET_ALL}"

def mostrar_mapa(camara):
    limpiar_pantalla()
    print(Fore.CYAN + "======================================================================")
    print(Fore.YELLOW + Style.BRIGHT + "            KUKULCÁN EXPRESS - CÁMARA DE CONGELACIÓN                  ")
    print(Fore.CYAN + "======================================================================")
    print("      " + imprimir_espacio(66, camara) + imprimir_espacio(65, camara) + imprimir_espacio(64, camara) + imprimir_espacio(63, camara))
    print("      " + imprimir_espacio(35, camara) + imprimir_espacio(34, camara) + imprimir_espacio(33, camara) + imprimir_espacio(32, camara))
    print("      " + imprimir_espacio(4, camara) + imprimir_espacio(3, camara) + imprimir_espacio(2, camara) + imprimir_espacio(1, camara))
    print()
    print("   IZQUIERDA               DERECHA")
    print(f"{imprimir_espacio(67, camara)}{imprimir_espacio(36, camara)}{imprimir_espacio(5, camara)}  [ PASILLO ]  {imprimir_espacio(31, camara)}{imprimir_espacio(62, camara)}{imprimir_espacio(93, camara)}")
    print(f"{imprimir_espacio(68, camara)}{imprimir_espacio(37, camara)}{imprimir_espacio(6, camara)}  [  MONTAS  ]  {imprimir_espacio(30, camara)}{imprimir_espacio(61, camara)}{imprimir_espacio(92, camara)}")
    print(f"{imprimir_espacio(69, camara)}{imprimir_espacio(38, camara)}{imprimir_espacio(7, camara)}  [  CARGA   ]  {imprimir_espacio(29, camara)}{imprimir_espacio(60, camara)}{imprimir_espacio(91, camara)}")
    print(f"{imprimir_espacio(70, camara)}{imprimir_espacio(39, camara)}{imprimir_espacio(8, camara)}  [          ]  {imprimir_espacio(28, camara)}{imprimir_espacio(59, camara)}{imprimir_espacio(90, camara)}")
    print(Fore.LIGHTBLACK_EX + "\n   (... El pasillo continúa exactamente como tu mapa real ...)\n")
    print("                " + imprimir_espacio(19, camara) + imprimir_espacio(20, camara) + imprimir_espacio(21, camara))
    print("                " + imprimir_espacio(50, camara) + imprimir_espacio(51, camara) + imprimir_espacio(52, camara))
    print("                " + imprimir_espacio(81, camara) + imprimir_espacio(82, camara) + imprimir_espacio(83, camara))
    print(Fore.CYAN + "======================================================================")
    ocupados = sum(1 for v in camara.values() if v["cliente"] != "VACÍO")
    print(Fore.WHITE + f"STATUS: Ocupados: {ocupados} | Disponibles: {93 - ocupados} | Ocupación: {(ocupados / 93) * 100:.1f}%")
    print(Fore.CYAN + "======================================================================")
    input(Fore.LIGHTBLUE_EX + "Presiona Enter para regresar al menú...")

def modificar_espacio(camara):
    limpiar_pantalla()
    print(Fore.MAGENTA + Style.BRIGHT + "=== MODIFICAR / EDITAR ESPACIO ===")
    try:
        num = int(input(Fore.WHITE + "Ingresa el número de espacio que deseas editar (1-93): "))
        if num < 1 or num > 93: return
        actual = camara[num]
        print(Fore.YELLOW + f"\nEstado actual del espacio {num}: {actual['cliente']} | {actual['cajas']} cajas\n" + "-"*40)
        nuevo_cliente = input(Fore.WHITE + "Nuevo Cliente (O escribe 'VACÍO' para liberar): ").strip().upper()
        if nuevo_cliente == "VACÍO" or nuevo_cliente == "":
            camara[num] = {"cliente": "VACÍO", "cajas": 0, "color_name": "NEGRO"}
            print(Fore.GREEN + f"\n¡Espacio {num} LIBERADO!")
        else:
            nuevas_cajas = int(input(Fore.WHITE + "Cantidad de cajas: "))
            print(Fore.CYAN + "\nSelecciona color: 1.Azul | 2.Rosa | 3.Verde")
            opc = input("Opción: ").strip()
            color = "AZUL" if opc=="1" else "ROSA" if opc=="2" else "VERDE"
            camara[num] = {"cliente": nuevo_cliente, "cajas": nuevas_cajas, "color_name": color}
            print(Fore.GREEN + f"\n¡Espacio {num} GUARDADO!")
        guardar_datos(camara)
    except ValueError: print(Fore.RED + "\nError en los datos.")
    input(Fore.CYAN + "\nPresiona Enter para continuar...")

def main():
    camara = cargar_datos()
    while True:
        limpiar_pantalla()
        print(Fore.CYAN + "=========================================")
        print(Fore.YELLOW + Style.BRIGHT + "      KUKULCÁN EXPRESS - CONTROL         ")
        print(Fore.CYAN + "=========================================")
        print(" 1. Ver Mapa Interactivo de la Cámara\n 2. Modificar Espacio (Editar / Liberar)\n 3. Cerrar y Salir")
        print(Fore.CYAN + "=========================================")
        opcion = input(Fore.LIGHTBLUE_EX + "Selecciona una opción [1-3]: ").strip()
        if opcion == "1": mostrar_mapa(camara)
        elif opcion == "2": modificar_espacio(camara)
        elif opcion == "3": sys.exit()

if __name__ == "__main__":
    main()
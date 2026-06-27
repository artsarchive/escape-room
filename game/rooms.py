# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — Definição das salas, objetos e enigmas
# ─────────────────────────────────────────────────────────────────

# Estrutura de uma sala:
# {
#   "description": str           — texto narrativo exibido ao entrar
#   "objects": {
#       "nome_objeto": {
#           "description": str   — texto ao examinar
#           "takeable": bool     — pode ser pego
#           "hidden": bool       — não aparece na listagem inicial
#           "reveals": str|None  — revela outro objeto ao examinar
#           "use_with": {        — combinar item do inventário com este objeto
#               "item": str,
#               "result_msg": str,
#               "unlocks": str|None   — destrava uma saída ou objeto
#           }
#       }
#   },
#   "exits": {
#       "norte"|"sul"|"leste"|"oeste": {
#           "room": str,         — chave da sala destino
#           "locked": bool,
#           "locked_msg": str,
#           "key": str|None      — item do inventário que abre
#       }
#   },
#   "hints": [str]               — dicas progressivas para esta sala
# }

ROOMS: dict = {

    # ── Sala 1: Laboratório ──────────────────────────────────────
    "laboratorio": {
        "description": (
            "Você está em um laboratório com cheiro forte de produtos químicos.\n"
            "A luz pisca no teto. Uma MESA DE TRABALHO ocupa o centro da sala.\n"
            "Há um COFRE embutido na parede norte e uma PORTA TRANCADA ao leste.\n"
            "Um QUADRO-NEGRO coberto de anotações está à sua esquerda."
        ),
        "objects": {
            "mesa": {
                "description": (
                    "A mesa está coberta de papéis e equipamentos quebrados. "
                    "Embaixo dela você enxerga uma CHAVE VERMELHA presa com fita adesiva."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": "chave_vermelha",
                "use_with": None,
            },
            "chave_vermelha": {
                "description": "Uma chave pequena com uma etiqueta vermelha desbotada.",
                "takeable": True,
                "hidden": True,
                "reveals": None,
                "use_with": None,
            },
            "quadro-negro": {
                "description": (
                    "Rabiscado no canto inferior do quadro há uma sequência: "
                    "\"4, 8, 15, 16, ??\".\n"
                    "O último número foi apagado, mas dá pra ver o risco — parece um 23."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": None,
            },
            "cofre": {
                "description": (
                    "Um cofre de 4 dígitos embutido na parede. "
                    "Está trancado. Há espaço para digitar um código."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": {
                    "item": "codigo_cofre",
                    "result_msg": (
                        "Você digita 4-8-15-23 no cofre. Um CLIQUE. "
                        "A porta do cofre se abre revelando uma CHAVE AZUL!"
                    ),
                    "unlocks": "chave_azul",
                },
            },
            "chave_azul": {
                "description": "Uma chave azul metálica. Parece nova.",
                "takeable": True,
                "hidden": True,
                "reveals": None,
                "use_with": None,
            },
            "porta_leste": {
                "description": "Uma porta de metal com fechadura azul. Está trancada.",
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": {
                    "item": "chave_azul",
                    "result_msg": "A chave azul encaixa perfeitamente. A porta range e abre!",
                    "unlocks": "saida_leste",
                },
            },
            "lixeira": {
                "description": (
                    "Uma lixeira industrial. Dentro há um papel amassado com "
                    "a anotação: \"o código é a sequência — use os 4 primeiros números\"."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": "codigo_cofre",
                "use_with": None,
            },
            "codigo_cofre": {
                "description": "Você sabe que o código é: 4-8-15-23.",
                "takeable": True,
                "hidden": True,
                "reveals": None,
                "use_with": None,
            },
        },
        "exits": {
            "leste": {
                "room": "corredor",
                "locked": True,
                "locked_msg": "A porta leste está trancada com uma fechadura azul.",
                "key": "chave_azul",
            }
        },
        "hints": [
            "Examine todos os objetos visíveis. Alguns escondem surpresas.",
            "O quadro-negro tem uma sequência de números. A lixeira pode complementar essa informação.",
            "O código do cofre usa os 4 primeiros números da sequência no quadro: 4, 8, 15 e o da lixeira.",
            "Código do cofre: 4-8-15-23. Dentro há uma chave que abre a porta leste.",
        ],
    },

    # ── Sala 2: Corredor ─────────────────────────────────────────
    "corredor": {
        "description": (
            "Um corredor estreito e mal iluminado. Há FOTOGRAFIAS desbotadas nas paredes.\n"
            "Uma CAIXA DE FUSÍVEIS aberta está ao fundo.\n"
            "Ao norte, uma PORTA DE MADEIRA. A oeste fica o laboratório."
        ),
        "objects": {
            "fotografias": {
                "description": (
                    "Fotos antigas de cientistas. Em uma delas, algo escrito atrás: "
                    "\"A saída está onde a luz não chega. Gire o fusível C3.\""
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": None,
            },
            "caixa_de_fusíveis": {
                "description": (
                    "Uma caixa com 6 fusíveis rotulados A1, A2, B1, B2, C1... e C3 está faltando.\n"
                    "Há um espaço vazio marcado C3."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": {
                    "item": "fusivel_c3",
                    "result_msg": (
                        "Você encaixa o fusível C3. As luzes do corredor piscam e "
                        "a PORTA DE MADEIRA ao norte destrava com um CLIQUE alto."
                    ),
                    "unlocks": "saida_norte",
                },
            },
            "tapete": {
                "description": "Um tapete surrado. Levantando a ponta, você encontra um FUSÍVEL C3 escondido!",
                "takeable": False,
                "hidden": False,
                "reveals": "fusivel_c3",
                "use_with": None,
            },
            "fusivel_c3": {
                "description": "Um fusível cilíndrico com a etiqueta C3.",
                "takeable": True,
                "hidden": True,
                "reveals": None,
                "use_with": None,
            },
            "porta_norte": {
                "description": "Uma porta de madeira pesada. Está trancada eletronicamente.",
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": None,
            },
        },
        "exits": {
            "oeste": {
                "room": "laboratorio",
                "locked": False,
                "locked_msg": "",
                "key": None,
            },
            "norte": {
                "room": "sala_final",
                "locked": True,
                "locked_msg": "A porta de madeira está trancada eletronicamente.",
                "key": "fusivel_c3",
            },
        },
        "hints": [
            "Examine tudo no corredor, inclusive objetos no chão.",
            "As fotografias revelam uma instrução importante sobre a caixa de fusíveis.",
            "Levante o tapete. O fusível que falta está escondido lá.",
            "Coloque o fusível C3 na caixa de fusíveis para abrir a porta norte.",
        ],
    },

    # ── Sala 3: Sala Final ───────────────────────────────────────
    "sala_final": {
        "description": (
            "Uma sala escura. No centro há um TERMINAL DE COMPUTADOR ligado.\n"
            "Na tela: \"INSIRA A SENHA MESTRE PARA ABRIR A SAÍDA\".\n"
            "Uma PLACA NA PAREDE e um DIÁRIO ABERTO estão sobre uma mesa.\n"
            "A SAÍDA PRINCIPAL está ao leste — trancada com cadeado eletrônico."
        ),
        "objects": {
            "terminal": {
                "description": (
                    "O terminal exibe um campo de senha. "
                    "Abaixo da tela, gravado no plástico: \"a senha é o nome do projeto\"."
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": {
                    "item": "senha_mestre",
                    "result_msg": (
                        "Você digita PROMETHEUS no terminal. "
                        "A tela fica verde: ACESSO CONCEDIDO. "
                        "O CADEADO da saída principal se abre com um estralo!"
                    ),
                    "unlocks": "saida_principal",
                },
            },
            "placa_na_parede": {
                "description": (
                    "Uma placa de metal: "
                    "\"PROJETO PROMETHEUS — Iniciado em 1987. Nunca concluído.\""
                ),
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": None,
            },
            "diário": {
                "description": (
                    "Última entrada do diário: "
                    "\"Se alguém encontrar isso, a senha é o nome do nosso projeto. "
                    "Boa sorte.\""
                ),
                "takeable": False,
                "hidden": False,
                "reveals": "senha_mestre",
                "use_with": None,
            },
            "senha_mestre": {
                "description": "Você sabe que a senha mestre é: PROMETHEUS.",
                "takeable": True,
                "hidden": True,
                "reveals": None,
                "use_with": None,
            },
            "saida_principal": {
                "description": "A saída principal. Um cadeado eletrônico a mantém fechada.",
                "takeable": False,
                "hidden": False,
                "reveals": None,
                "use_with": None,
            },
        },
        "exits": {
            "sul": {
                "room": "corredor",
                "locked": False,
                "locked_msg": "",
                "key": None,
            },
            "leste": {
                "room": "__ESCAPE__",   # destino especial = vitória
                "locked": True,
                "locked_msg": "A saída principal está trancada com cadeado eletrônico.",
                "key": "senha_mestre",
            },
        },
        "hints": [
            "Examine todos os objetos na sala. Você precisa encontrar a senha.",
            "A placa na parede e o diário juntos revelam o nome do projeto.",
            "O nome do projeto está na placa: PROMETHEUS. Essa é a senha do terminal.",
            "Use 'usar senha_mestre em terminal' para digitar a senha e abrir a saída.",
        ],
    },
}

INITIAL_ROOM = "laboratorio"

# ─────────────────────────────────────────────────────────────────
#  ERP/1.0 — A Grande Fuga do Hospital (Campanha Co-op Avançada)
# ─────────────────────────────────────────────────────────────────

MAPS: dict = {
    "hospital": {
        "name": "🏥 Hospital Abandonado (Co-op Avançado)",
        "initial_rooms": {0: "recepcao", 1: "sala_de_forca"},
        "rooms": {

            # ════════════ CAMINHO DO JOGADOR 1 ════════════

            "recepcao": {
                "description": "Você está na recepção às escuras.\nA PORTA LESTE (Consultório) está trancada.\nHá um TERMINAL DE MONITORAMENTO apagado e uma PLACA DE ALIMENTAÇÃO na parede.",
                "objects": {
                    "placa_de_alimentacao": {"description": "Aviso: 'Gerador primário configurado para 440V. Repasse à manutenção.'.", "takeable": False, "hidden": False, "assigned_to_role": 0},
                    "terminal_de_monitoramento": {"description": "O monitor está sem energia. O servidor central fica na Sala de Força.", "takeable": False, "hidden": False, "assigned_to_role": 0},
                    "porta_leste": {
                        "description": "Porta de vidro reforçado com painel numérico (colocar <senha> na porta).", "takeable": False, "hidden": False,
                        "use_with": {"item": "8520", "result_msg": "A luz verde acende e a porta do Consultório se abre!", "unlocks": "saida_leste"}
                    }
                },
                "exits": {"leste": {"room": "consultorio", "locked": True, "locked_msg": "Trancada por senha.", "key": "8520"}},
                "hints": ["Passe a voltagem para seu parceiro via chat.", "Aguarde a energia ligar para examinar o terminal."]
            },

            "consultorio": {
                "description": "Um consultório médico revirado.\nA PORTA NORTE (Ala Médica) tem uma fechadura biométrica vermelha.\nHá um DIPLOMA na parede e um MANUAL DE MANUTENÇÃO rasgado.",
                "objects": {
                    "diploma": {"description": "Diploma do Chefe da Cirurgia: 'Dr. Augusto. Hospital fundado no glorioso ano de 1968'.", "takeable": False, "hidden": False, "assigned_to_role": 0},
                    "manual_manutencao": {"description": "Nota técnica: 'O código de emergência da válvula de vapor do almoxarifado é 314'.", "takeable": False, "hidden": False, "assigned_to_role": 0},
                    "cracha_caido": {"description": "Crachá do médico chefe. 'Acesso Nível 4 - ID: 7701'.", "takeable": False, "hidden": False, "assigned_to_role": 0},
                    "porta_norte": {"description": "O leitor indica: 'Bloqueio de TI ativado. Solicite liberação remota ao servidor no Subsolo.'", "takeable": False, "hidden": False, "assigned_to_role": 0}
                },
                "exits": {"norte": {"room": "ala_medica", "locked": True, "locked_msg": "Requer liberação remota de TI.", "key": "liberacao_ti"}},
                "hints": ["Leia o diploma, o manual e o crachá. Repasse TUDO para o seu parceiro!"]
            },

            "ala_medica": {
                "description": "Uma ala cheia de macas enferrujadas.\nA PORTA LESTE leva ao Corredor Central (Saída).\nHá um COFRE MÉDICO encravado na parede e um PRONTUÁRIO na cama.",
                "objects": {
                    "prontuario": {"description": "Anotação rabiscada: 'A senha das ferramentas do zelador no subsolo é 1234'.", "takeable": False, "hidden": False},
                    "cofre_medico": {
                        "description": "Cofre pesado (colocar <codigo> no cofre).", "takeable": False, "hidden": False,
                        "use_with": {"item": "9999", "result_msg": "O cofre estala e abre. Dentro está a CHAVE ESQUERDA!", "unlocks": "chave_esquerda"}
                    },
                    "chave_esquerda": {"description": "Uma chave maciça com a letra L.", "takeable": True, "hidden": True, "assigned_to_role": 0}
                },
                "exits": {"leste": {"room": "corredor_central", "locked": False}},
                "hints": ["Passe a senha das ferramentas para o parceiro e peça a senha do cofre."]
            },


            # ════════════ CAMINHO DO JOGADOR 2 ════════════

            "sala_de_forca": {
                "description": "Sala abafada com cheiro de ozônio.\nA PORTA SUL (Almoxarifado) está fechada com um teclado antigo.\nHá um PAINEL DE CONTROLE gigantesco.",
                "objects": {
                    "painel_de_controle": {"description": "Visor piscando: 'Insira a voltagem primária' (colocar <voltagem> no painel).", "takeable": False, "hidden": False, "assigned_to_role": 1},
                    "porta_sul": {
                        "description": "Fechadura antiga. Uma etiqueta diz: 'Senha = Ano de Fundação do Hospital' (colocar <ano> na porta).", "takeable": False, "hidden": False,
                        "use_with": {"item": "1968", "result_msg": "A porta destranca e você pode ir para o sul!", "unlocks": "saida_sul"}
                    }
                },
                "exits": {"sul": {"room": "almoxarifado", "locked": True, "locked_msg": "Trancada.", "key": "1968"}},
                "hints": ["Pergunte a voltagem ao seu parceiro.", "Pergunte se ele achou a data de fundação."]
            },

            "almoxarifado": {
                "description": "A sala está coberta por uma névoa espessa.\nA PORTA LESTE (Subsolo) está bloqueada por um vazamento de VAPOR ESCALDANTE.\nHá uma VÁLVULA presa na parede e uma FICHA DE PACIENTE.",
                "objects": {
                    "ficha_de_paciente": {"description": "Ficha confidencial: 'Acesso do cofre da Ala Médica alterado para 9999'.", "takeable": False, "hidden": False, "assigned_to_role": 1},
                    "valvula": {
                        "description": "Possui um cadeado com 3 dígitos (colocar <codigo> na valvula).", "takeable": False, "hidden": False,
                        "use_with": {"item": "314", "result_msg": "Você gira a válvula. O vapor se dissipa, liberando a passagem para o leste!", "unlocks": "saida_leste"}
                    }
                },
                "exits": {"leste": {"room": "subsolo", "locked": True, "locked_msg": "O vapor escaldante o impede de passar.", "key": "314"}},
                "hints": ["Peça o código da válvula de vapor para o seu parceiro.", "Repasse a senha do cofre para ele."]
            },

            "subsolo": {
                "description": "O porão de manutenção.\nA PORTA NORTE leva ao Corredor Central.\nHá um SERVIDOR DE TI e uma CAIXA DE FERRAMENTAS.",
                "objects": {
                    "servidor_de_ti": {"description": "O console diz: 'Insira o ID do Médico Chefe para forçar liberação de portas na Ala Médica' (colocar <id> no servidor).", "takeable": False, "hidden": False, "assigned_to_role": 1},
                    "caixa_de_ferramentas": {
                        "description": "Caixa de aço travada com cadeado (colocar <senha> na caixa).", "takeable": False, "hidden": False,
                        "use_with": {"item": "1234", "result_msg": "O cadeado cai! Dentro está a CHAVE DIREITA.", "unlocks": "chave_direita"}
                    },
                    "chave_direita": {"description": "Uma chave maciça com a letra R.", "takeable": True, "hidden": True, "assigned_to_role": 1}
                },
                "exits": {"norte": {"room": "corredor_central", "locked": False}},
                "hints": ["Peça a senha das ferramentas e o ID do médico para o seu parceiro."]
            },

            # ════════════ ENCONTRO FINAL ════════════

            "corredor_central": {
                "description": "O vasto Corredor Central do hospital.\nÀ frente está a imponente SAÍDA PRINCIPAL. O painel exige as duas chaves físicas operadas simultaneamente.",
                "objects": {
                    "dispositivo_esquerdo": {"description": "Painel esquerdo. Use sua chave aqui.", "takeable": False, "use_with": {"item": "chave_esquerda", "result_msg": "Chave L travada na posição!", "unlocks": "saida_norte"}},
                    "dispositivo_direito": {"description": "Painel direito. Use sua chave aqui.", "takeable": False, "use_with": {"item": "chave_direita", "result_msg": "Chave R travada na posição!", "unlocks": "saida_norte"}},
                    "porta_saida": {"description": "Porta de aço dupla trancada.", "takeable": False}
                },
                "exits": {
                    "norte": {"room": "__ESCAPE__", "locked": True,  "locked_msg": "A porta não cede. Usem as chaves nos dispositivos."},
                    "oeste": {"room": "ala_medica",  "locked": False, "locked_msg": ""},
                    "sul":   {"room": "subsolo",     "locked": False, "locked_msg": ""}
                },
                "hints": [
                    "Cada jogador precisa usar sua chave no dispositivo correspondente desta sala.",
                    "P1 usa chave_esquerda no dispositivo_esquerdo. P2 usa chave_direita no dispositivo_direito.",
                    "Ambos precisam girar as chaves. Depois é só ir norte para escapar!"
                ]
            }
        }
    }
}

ROOMS = MAPS["hospital"]["rooms"]
INITIAL_ROOM = "recepcao"
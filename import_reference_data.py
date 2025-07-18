#!/usr/bin/env python
# import_reference_data_direct.py
import os
import sys
import argparse
import django
from django.db import transaction

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings_local_django")
django.setup()

from apps.sechic.models import Color, Size, Brand
from apps.moloni.models import Moloni
from django.contrib.auth import get_user_model

def get_company(company_id=None):
    try:
        if company_id:
            company = Moloni.objects.get(company_id=company_id)
            print(f"Usando empresa Moloni com company_id={company_id}")
            return company
        
        company = Moloni.objects.first()
        if company:
            print(f"Usando empresa Moloni existente: {company.company_id}")
            return company
        
    
        User = get_user_model()
        try:
            default_user = User.objects.get(username='admin')  # Assumindo que existe um usuário 'admin'
            company.users.add(default_user)
        except User.DoesNotExist:
            print("AVISO: Usuário 'admin' não encontrado. Criando empresa sem usuários associados.")
        print(f"Empresa padrão criada: {company.company_id}")
        return company
    except Moloni.DoesNotExist:
        raise Exception(f"Empresa Moloni com company_id={company_id} não encontrada.")
    except Exception as e:
        raise Exception(f"Erro ao obter/criar empresa Moloni: {str(e)}")

def import_reference_data(company_id=None):
    """
    Importa dados de referência diretamente para os modelos do Django
    """
    try:
        # Dados pré-definidos
        company = get_company(company_id)

        colors_data = [
            ('1', 'Branco'),
            ('2', 'Vermelho'),
            ('3', 'Verde'),
            ('4', 'Castanho'),
            ('5', 'Amarelo'),       
            ('6', 'Lilás'),
            ('7', 'Rosa'),
            ('8', 'Azul'),
            ('9', 'Laranja'),
            ('10', 'Preto'),
            ('11', 'Cinza'),
            ('12', 'Bege'),
            ('13', 'Camel'),
            ('14', 'Coral'),
            ('15', 'Chocolate'),
            ('16', 'Nude'),
            ('17', 'Dourado'),
            ('18', 'Gelo'),
            ('19', 'Grená'),
            ('20', 'Turquesa'),
            ('21', 'Prata'),
            ('22', 'Bordeaux'),
            ('23', 'Roxo'),
            ('24', 'Violeta'),
            ('25', 'Salmão'),
            ('26', 'Bronze'),
            ('27', 'Cereja'),
            ('28', 'Fucsia'),
            ('29', 'Marfim'),
            ('30', 'Tijolo'),
            ('31', 'Azul Escuro'),
            ('32', 'Azul Claro'),
            ('33', 'Multicolor'),
            ('34', 'Verde Escuro'),
            ('35', 'Verde Claro')
        ]
        
        # Tamanhos (code, value)
        sizes_data = [
            ('1', 'XS'),
            ('2', 'S'),
            ('3', 'M'),
            ('4', 'L'),
            ('5', 'XL'),
            ('6', 'XXL'),
            ('7', 'XXXL'),
            ('8', '31'),
            ('9', '32'),
            ('10', '33'),
            ('11', '34'),
            ('12', '35'),
            ('13', '36'),
            ('14', '37'),
            ('15', '38'),
            ('16', '39'),
            ('17', '40'),
            ('18', '42'),
            ('19', '44'),
            ('20', '46'),
            ('21', '48'),
            ('22', '50'),
            ('23', '52'),
            ('24', '54'),
            ('25', '56'),
            ('26', '58'),
            ('27', '2'),
            ('28', '4'),
            ('29', '6'),
            ('30', '8'),
            ('31', '10'),
            ('32', '12'),
            ('33', '14'),
            ('34', '16'),
            ('35', 'TU'),
            ('36', '28'),
            ('37', '29'),
            ('38', '30'),
            ('39', '26'),
            ('40', '27'),
            ('41', '39-40'),
            ('42', '41-42'),
            ('43', '43-44'),
            ('44', '41'),
            ('45', '43'),
            ('46', '85'),
            ('47', '90'),
            ('48', '95'),
            ('49', '100'),
            ('50', '39-42'),
            ('51', '43-46'),
            ('52', '6.5'),
            ('53', '7'),
            ('54', '7.5'),
            ('55', '8.5'),
            ('56', '9'),
            ('57', '105'),
            ('58', '40-46'),
            ('59', '110'),
            ('60', 'XXS'),
            ('61', '1'),
            ('62', '60'),
            ('63', 'XXXXL'),
            ('64', '40-42'),
            ('65', '43-45'),
            ('66', '5,5'),
            ('67', '115'),
            ('68', '57'),
            ('69', '45'),
            ('70', '25')
        ]
        
        # Marcas (name)
        brands_data = [
            'HUGO BOSS',
            'PAUL & SHARK',
            'LIU.JO',
            'LOVE MOSCHINO',
            'BRAX',
            'MEYER',
            'TWINSET',
            'WEEKEND/MAXMARA',
            'MARELLA',
            'TOMMY HILFIGER',
            'GANT',
            'LEBEK',
            'BOUTIQUE MOSCHINO',
            'COCCINELLI',
            'DIELMAR',
            'ESCORPION',
            'NAULOVER',
            'MICAELA LUISA',
            'RALPH LAUREN',
            'KOTTAS & MANTSIOS',
            'CORTY',
            'MAXMARA',
            'PINKO',
            'AT.P.CO',
            'PINKO-CRIS CONF S.p.A',
            'GOLDEN SEASON',
            'BENNETT'
        ]
        
        
        # Usar transação para garantir que todos os dados sejam importados ou nenhum
        with transaction.atomic():
            # 1. Importar Cores
            print("Importando cores...")
            for code, name in colors_data:
                Color.objects.update_or_create(
                    code=code,
                    defaults={'name': name,'company': company},
                )
            print(f"Total de cores importadas: {len(colors_data)}")
            
            # 2. Importar Tamanhos
            print("Importando tamanhos...")
            for code, value in sizes_data:
                Size.objects.update_or_create(
                    code=code,
                    defaults={'value': value,'company': company},

                )
            print(f"Total de tamanhos importados: {len(sizes_data)}")
            
            # 4. Importar Marcas
            print("Importando marcas...")
            for name in brands_data:
                Brand.objects.update_or_create(name=name,defaults={
                        'company': company 
                    })
            print(f"Total de marcas importadas: {len(brands_data)}")
            


        print("Importação concluída com sucesso!")
        
    except Exception as e:
        print(f"Erro ao importar dados: {str(e)}")
        import traceback
        traceback.print_exc()


# Função para verificar se os modelos estão vazios e alertar o usuário
def check_existing_data():
    """
    Verifica se já existem dados nos modelos e alerta o usuário
    """
    colors_count = Color.objects.count()
    sizes_count = Size.objects.count()
    brands_count = Brand.objects.count()
    
    existing_data = False
    if colors_count > 0:
        print(f"ATENÇÃO: Já existem {colors_count} cores no banco de dados.")
        existing_data = True
    if sizes_count > 0:
        print(f"ATENÇÃO: Já existem {sizes_count} tamanhos no banco de dados.")
        existing_data = True
    if brands_count > 0:
        print(f"ATENÇÃO: Já existem {brands_count} marcas no banco de dados.")
        existing_data = True
    
    if existing_data:
        response = input("Deseja continuar e possivelmente sobrescrever dados existentes? (s/n): ")
        if response.lower() != 's':
            print("Operação cancelada pelo usuário.")
            return False
    
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Importa dados de referência para o banco de dados Django.")
    parser.add_argument('--company_id', type=int, help='ID da empresa Moloni para associar aos dados.')
    args = parser.parse_args()
    print("=== Importação de Dados de Referência ===")
    print("Este script irá importar cores, tamanhos, marcas e fornecedores para o banco de dados Django.")
    
    # Verificar se já existem dados e confirmar com o usuário
    if check_existing_data():
        try:
            import_reference_data(company_id=args.company_id)
            print("\n=== Importação concluída com sucesso! ===")
        except Exception as e:
            print(f"\n=== Erro durante a importação: {str(e)} ===")
import re
from datetime import datetime

import oaipmh
import oaipmh.error
import oaipmh.metadata
import oaipmh.server
from django.urls import reverse
from lxml import etree
from lxml.builder import ElementMaker

from sapl.base.models import CasaLegislativa, AppConfig
from sapl.lexml.models import LexmlPublicador
from sapl.norma.models import NormaJuridica


class OAILEXML():
    """
        Padrao OAI do LeXML
        Esta registrado sobre o nome 'oai_lexml'
    """

    def __init__(self, prefix):
        self.prefix = prefix
        self.ns = {'oai_lexml': 'http://www.lexml.gov.br/oai_lexml', }
        self.schemas = {'oai_lexml': 'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd'}

    def __call__(self, element, metadata):
        data = metadata.record
        value = etree.XML(data['metadata'])
        element.append(value)


class OAIServer():
    """
        An OAI-2.0 compliant oai server.
        Underlying code is based on pyoai's oaipmh.server'
    """

    XSI_NS = 'http://www.w3.org/2001/XMLSchema-instance'
    ns = {'lexml': 'http://www.lexml.gov.br/oai_lexml'}
    schema = {'oai_lexml': 'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd'}

    def __init__(self, config={}):
        self.config = config

    # utilizado?
    # def get_asset_path(self, internal_id, asset):
    #     return os.path.abspath(
    #         os.path.join(self.base_asset_path,
    #                      internal_id,
    #                      asset['filename']))

    def identify(self):
        result = oaipmh.common.Identify(
            repositoryName=self.config['titulo'],
            baseURL=self.config['base_url'],
            protocolVersion='2.0',
            adminEmails=self.config['email'],
            earliestDatestamp=datetime(2001, 1, 1, 10, 00),
            deletedRecord='transient',
            granularity='YYYY-MM-DDThh:mm:ssZ',
            compression=['identity'],
            toolkit_description=False)
        if not self.config['descricao']:
            result.add_description(self.config['descricao'])
        return result

    # def get_namespace(self):
    #     return self.ns[self.prefix]
    #
    # def get_schema_location(self):
    #     return self.schemas[self.prefix]
    #
    # # utilizado?
    # def listMetadataFormats(self, identifier=None):
    #     result = []
    #     for prefix in self.config['metadata_prefixes']:
    #         writer = (lambda prefix_param: OAILEXML(prefix_param))(prefix)  # Get writer
    #         ns = writer.get_namespace()
    #         schema = writer.get_schema_location()
    #         result.append((prefix, schema, ns))
    #     return result

    def check_metadata_prefix(self, metadata_prefix):
        if not metadata_prefix in self.config['metadata_prefixes']:
            raise oaipmh.error.CannotDisseminateFormatError

    def create_header_and_metadata(self, record):
        header = self.create_header(record)
        metadata = oaipmh.common.Metadata(None, record['metadata'])
        metadata.record = record
        return header, metadata

    def listRecords(self, metadataPrefix, set=None, from_=None, until=None, cursor=0, batch_size=10):
        self.check_metadata_prefix(metadataPrefix)
        for record in self.list_query(set, from_, until, cursor, batch_size):
            header, metadata = self.create_header_and_metadata(record)
            yield header, metadata, None  # NONE?????

    def create_header(self, record):
        oai_id = (lambda internal_id: "oai:{}".format(internal_id))(record['record']['id'])  # Get OAI id
        timestamp = record['record']['when_modified']
        timestamp = timestamp.replace(tzinfo=None)
        sets = []
        deleted = record['record']['deleted']
        return oaipmh.common.Header(None, oai_id, timestamp, sets, deleted)

    # def listIdentifiers(self, metadata_prefix, dataset=None, start=None, end=None, cursor=0, batch_size=10):
    #     self.check_metadata_prefix(metadata_prefix)
    #     for record in self.list_query(dataset, start, end, cursor, batch_size):
    #         yield self.create_header(record)

    # def getRecord(self, metadata_prefix, identifier):
    #     header = None
    #     metadata = None
    #     self.check_metadata_prefix(metadata_prefix)
    #     for record in self.list_query(identifier=identifier):
    #         header, metadata = self.create_header_and_metadata(record)
    #
    #     # pega o ultimo header??????
    #     if not header:
    #         raise oaipmh.error.IdDoesNotExistError(identifier)
    #     return header, metadata, None

    def list_query(self, dataset=None, from_=None, until=None, cursor=0, batch_size=10, identifier=None):
        if identifier:
            identifier = (lambda oai_id: int(oai_id.split('/').pop()))(identifier)  # Get internal id
        else:
            identifier = ''

        if dataset:
            dataset = (lambda oai_setspec_id: oai_setspec_id[4:])(dataset)  # Get internal set id

        # TODO: verificar se a data eh UTC
        now = datetime.now()
        # until nunca deve ser no futuro
        if not until or until > now:
            until = now

        return self.oai_query(offset=cursor,
                              batch_size=batch_size,
                              from_date=from_,
                              until_date=until,
                              identifier=identifier)

    def monta_id(self, norma):
        """ Funcao que monta o id do objeto do LexML
        """

        casa = (lambda: CasaLegislativa.objects.first())()  # Get casa legislativa

        if norma:
            num = len(casa.endereco_web.split('.'))
            dominio = '.'.join(casa.endereco_web.split('.')[1:num])

            prefixo_oai = '{}.{}:sapl/'.format(casa.sigla.lower(), dominio)
            numero_interno = norma.numero
            tipo_norma = norma.tipo.equivalente_lexml
            ano_norma = norma.ano

            identificador = '{}{};{};{}'.format(prefixo_oai, tipo_norma, ano_norma, numero_interno)

            return identificador
        else:
            return None

    def get_esfera_federacao(self):
        appconfig = AppConfig.objects.first()

        return appconfig.esfera_federacao

    def monta_urn(self, norma):
        """ Funcao que monta a URN do LexML
        """
        casa = (lambda: CasaLegislativa.objects.first())()  # Get casa legislativa
        esfera = self.get_esfera_federacao()

        if norma:
            url = self.config['base_url'] + reverse('sapl.norma:normajuridica_detail', kwargs={'pk': norma.numero})
            # url = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(numero)

            urn = 'urn:lex:br;'
            esferas = {'M': 'municipal', 'E': 'estadual'}

            # TODO: municipio e uf são a mesma coisa?
            municipio = casa.municipio.lower()
            for i in re.findall('\s', municipio):
                municipio = municipio.replace(i, '.')

            # solucao temporaria
            if re.search('\.de\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall('\.de\.', municipio)][0]
            if re.search('\.da\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall('\.da\.', municipio)][0]
            if re.search('\.das\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall('\.das\.', municipio)][0]
            if re.search('\.do\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall('\.do\.', municipio)][0]
            if re.search('\.dos\.', municipio):
                municipio = [municipio.replace(i, '.') for i in re.findall('\.dos\.', municipio)][0]

            uf = casa.municipio.lower()
            for i in re.findall('\s', uf):
                uf = uf.replace(i, '.')

            # solucao temporaria
            if re.search('\.de\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall('\.de\.', uf)][0]
            if re.search('\.da\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall('\.da\.', uf)][0]
            if re.search('\.das\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall('\.das\.', uf)][0]
            if re.search('\.do\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall('\.do\.', uf)][0]
            if re.search('\.dos\.', uf):
                uf = [uf.replace(i, '.') for i in re.findall('\.dos\.', uf)][0]

            if esfera == 'M':
                urn += uf + ';'
                urn += municipio + ':'

                if norma.tipo.equivalente_lexml == 'regimento.interno' or norma.tipo.equivalente_lexml == 'resolucao':
                    urn += 'camara.municipal:'
                else:
                    urn += esferas[esfera] + ':'
            elif esfera == 'E':
                urn += uf + ':'
                urn += esferas[esfera] + ':'
            else:
                urn += ':'

            urn += norma.tipo.equivalente_lexml + ':'

            urn += norma.data.isoformat() + ';'

            if norma.tipo.equivalente_lexml == 'lei.organica' or norma.tipo.equivalente_lexml == 'constituicao':
                urn += norma.ano
            else:
                urn += norma.numero

            if norma.data_vigencia and norma.data_publicacao:
                urn += '@'
                urn += norma.data_vigencia.isoformat()
                urn += ';publicacao;'
                urn += norma.data_publicacao.isoformat()
            elif norma.data_publicacao:
                urn += '@'
                urn += 'inicio.vigencia;publicacao;' + norma.data_publicacao.isoformat()
            #            else:
            #                urn += 'inicio.vigencia;publicacao;'
            #
            #            if norma.data_publicacao:
            #                urn += norma.data_publicacao.isoformat()

            return urn
        else:
            return None

    def recupera_norma(self, offset, batch_size, from_date, until_date, identifier, esfera):
        kwargs = {'data__lte': until_date}

        if from_date:
            kwargs['data__gte'] = from_date

        if identifier:
            kwargs['numero'] = identifier

        if esfera:
            kwargs['esfera_federacao'] = esfera

        return NormaJuridica.objects.select_related('tipo').filter(**kwargs)[offset:offset + batch_size]

    def oai_query(self, offset=0, batch_size=10, from_date=None, until_date=None, identifier=None):
        esfera = self.get_esfera_federacao()
        offset = 0 if offset < 0 else offset
        batch_size = 10 if batch_size < 0 else batch_size
        until_date = datetime.now() if not until_date or until_date > datetime.now() else until_date

        normas = self.recupera_norma(offset, batch_size, from_date, until_date, identifier, esfera)

        for norma in normas:
            resultado = {}
            identificador = self.monta_id(norma)
            urn = self.monta_urn(norma)
            xml_lexml = self.monta_xml(urn, norma)

            resultado['tx_metadado_xml'] = xml_lexml
            # resultado['id_registro_item'] = resultado['name']
            # del resultado['name']
            # record['sets'] = record['sets'].strip().split(' ')
            # if resultado['sets'] == [u'']:
            #    resultado['sets'] = []
            resultado['cd_status'] = 'N'
            resultado['id'] = identificador
            resultado['when_modified'] = norma.timestamp
            resultado['deleted'] = 0
            #             if norma.ind_excluido == 1:
            #                 resultado['deleted'] = 1
            # #                resultado['cd_status'] = 'D'
            yield {'record': resultado,
                   #                   'sets': ['person'],
                   'metadata': resultado['tx_metadado_xml'],
                   #                   'assets':{}
                   }

    def monta_xml(self, urn, norma):
        # criacao do xml

        casa = (lambda: CasaLegislativa.objects.first())()  # Get casa legislativa

        # consultas
        publicador = LexmlPublicador.objects.first()
        if norma and publicador:
            url = self.config['base_url'] + reverse('sapl.norma:normajuridica_detail', kwargs={'pk': norma.numero})
            # url = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(cod_norma)

            E = ElementMaker()
            LEXML = ElementMaker(namespace=self.ns['lexml'], nsmap=self.ns)

            oai_lexml = LEXML.LexML()

            oai_lexml.attrib['{%s}schemaLocation' % self.XSI_NS] = '%s %s' % (
                'http://www.lexml.gov.br/oai_lexml',
                'http://projeto.lexml.gov.br/esquemas/oai_lexml.xsd')

            id_publicador = str(publicador.id_publicador)

            # montagem da epigrafe
            localidade = casa.municipio
            sigla_uf = casa.uf
            if norma.tipo.equivalente_lexml == 'lei.organica':
                epigrafe = '{} de {} - {}, de {}'.format(norma.tipo.descricao, localidade, sigla_uf, norma.ano)
            elif norma.tipo.equivalente_lexml == 'constituicao':
                epigrafe = '{} do Estado de {}, de {}'.format(norma.tipo.descricao, localidade, norma.ano)
            else:
                epigrafe = '{} n° {},  de {}'.format(norma.tipo.descricao, norma.numero,
                                                     self.data_converter_por_extenso_pysc(
                                                         norma.data))  # TODO: pegar isso

            ementa = norma.ementa
            indexacao = norma.indexacao

            formato = 'text/html'
            # TODO: recuperar formato correto do arquivo
            # id_documento = '{}_{}'.format(norma.numero, self.sapl_documentos.norma_juridica.nom_documento)
            # if hasattr(self.sapl_documentos.norma_juridica, id_documento):
            #     arquivo = getattr(self.sapl_documentos.norma_juridica, id_documento)
            #     url_conteudo = arquivo.absolute_url()
            #     formato = arquivo.content_type
            #     if formato == 'application/octet-stream':
            #         formato = 'application/msword'
            #     elif formato == 'image/ipeg':
            #         formato = 'image/jpeg'
            # else:
            #     url_conteudo = self.portal_url() + '/consultas/norma_juridica/norma_juridica_mostrar_proc?cod_norma=' + str(cod_norma)

            if norma.texto_integral:
                url_conteudo = self.config['base_url'] + norma.texto_integral.url
                formato = 'application/pdf'  # TODO: PEGAR O FORMATO DO ARQUIVO
            else:
                url_conteudo = self.config['base_url'] + reverse('sapl.norma:normajuridica_detail',
                                                                 kwargs={'pk': norma.numero})

            item_conteudo = E.Item(url_conteudo, formato=formato, idPublicador=id_publicador, tipo='conteudo')
            oai_lexml.append(item_conteudo)

            item_metadado = E.Item(url, formato='text/html', idPublicador=id_publicador, tipo='metadado')
            oai_lexml.append(item_metadado)

            documento_individual = E.DocumentoIndividual(urn)
            oai_lexml.append(documento_individual)
            oai_lexml.append(E.Epigrafe(epigrafe))  # TODO: epigrafe.decode('iso-8859-1')
            oai_lexml.append(E.Ementa(ementa))  # TODO: ementa.decode('iso-8859-1')
            if indexacao:
                oai_lexml.append(E.Indexacao(indexacao))  # TODO: indexacao.decode('iso-8859-1')
            return etree.tostring(oai_lexml)
        else:
            return None

    def data_converter_por_extenso_pysc(self, data):
        """
          Funcaoo: Converter a data do formato DD/MM/AAAA para
                  o formato AAAA/MM/DD, e depois converter em dia da semana
                  Ex: sexta-feira.

          Argumento: Data a ser convertida.

          Retorno: Dia da semana.
        """

        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro',
                 'Novembro', 'Dezembro']
        data = data.strftime('%d-%m-%Y')
        if data != '':
            mes = int(data[3:5])
            return data[0:2] + " de " + meses[int(mes - 1)] + " de " + data[6:]
        else:
            return ''


def OAIServerFactory(config={}):
    """Create a new OAI batching OAI Server given a config and
    a database"""
    for prefix in config['metadata_prefixes']:
        metadata_registry = oaipmh.metadata.MetadataRegistry()
        metadata_registry.registerWriter(prefix, OAILEXML(prefix))

    return oaipmh.server.BatchingServer(
        OAIServer(config),
        metadata_registry=metadata_registry,
        resumption_batch_size=config['batch_size']
    )


# TODO: RECUPERAR DA BASE DE DADOS
def get_config(url):
    config = {}
    config['titulo'] = 'cocalzinho'  # self.get_nome_repositorio()
    config['email'] = 'camara@cocalzinho.gov'  # self.get_email()
    config['base_url'] = (lambda url: url[:url.find('/', 8)])(url)  # Get base url
    config['metadata_prefixes'] = ['oai_lexml']
    config['descricao'] = 'ficticia'  # self.get_descricao_casa()
    config['batch_size'] = 10  # self.get_batch_size()
    config['content_type'] = None,
    config['delay'] = 0,
    config['base_asset_path'] = None
    return config


if __name__ == '__main__':
    """
        Para executar localmente (estando no diretório raiz):
        
        $ ./manage.py shell_plus
        
        Executar comando        
        %run sapl/lexml/OAIServer.py
    """
    oai_server = OAIServerFactory(get_config('http://127.0.0.1:8000/'))
    r = oai_server.handleRequest({'verb': 'ListRecords',
                                  'metadataPrefix': 'oai_lexml'
                                  })
    print(r.decode('UTF-8'))

from django.http import HttpResponse

from sapl.crud.base import CrudAux
from sapl.lexml.OAIServer import OAIServerFactory, get_config

from .models import LexmlProvedor, LexmlPublicador

LexmlProvedorCrud = CrudAux.build(LexmlProvedor, 'lexml_provedor')
LexmlPublicadorCrud = CrudAux.build(LexmlPublicador, 'lexml_publicador')


def lexml_request(request):
    config = get_config(request.get_raw_uri())  # Passa toda a url
    oai_server = OAIServerFactory(config)
    r = oai_server.handleRequest({'verb': 'ListRecords',
                                  'metadataPrefix': 'oai_lexml'
                                  })
    response = r.decode('UTF-8')
    return HttpResponse(response, content_type='text/xml')

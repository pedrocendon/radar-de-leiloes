"""Allowlisted HTTPS collectors, with public DNS addresses pinned per connection."""
import http.client
import ipaddress
import socket
import urllib.request
from urllib.parse import urlsplit
from collectors import Client, CollectError, NoRedirect


def public_addresses(host):
    addresses=list(dict.fromkeys(r[4][0] for r in socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)))
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise OSError('Destino não público recusado.')
    return addresses


class PublicConnection(http.client.HTTPSConnection):
    def connect(self):
        if self._tunnel_host or self.port!=443:raise OSError('Proxy ou porta não permitidos.')
        last=None
        for ip in public_addresses(self.host):
            try:
                sock=socket.create_connection((ip,443),self.timeout,self.source_address)
                try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
                except Exception:sock.close();raise
                return
            except OSError as exc:last=exc
        raise last or OSError('Não foi possível conectar.')


class PublicHandler(urllib.request.HTTPSHandler):
    def https_open(self,req):
        return self.do_open(PublicConnection,req,context=self._context)


def validate_url(url,hosts):
    try:
        p=urlsplit(url)
        if (len(url)>2048 or p.scheme!='https' or p.hostname not in hosts or
            p.port not in (None,443) or p.username or p.password or '\\' in url):
            raise ValueError()
    except (ValueError,TypeError):
        raise ValueError('Use um link HTTPS de um dos sites cadastrados, sem porta personalizada.') from None


class PublicClient(Client):
    def __init__(self,hosts):
        super().__init__();self.hosts=frozenset(hosts)
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect,PublicHandler())

    def raw(self,url):
        try:validate_url(url,self.hosts)
        except ValueError as exc:raise CollectError('bloqueado',str(exc)) from exc
        return super().raw(url)

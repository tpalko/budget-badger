from web.util.config import Config 

def config(get_response):

    def middleware(request):
        
        request.__setattr__('bbconfig', Config())
        response = get_response(request)
    
        return response 

    return middleware
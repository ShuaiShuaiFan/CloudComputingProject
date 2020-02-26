import aiml
import sys
import os
def get_module_dir(name):
    path = getattr(sys.modules[name], '__file__', None)
    if not path:
        raise AttributeError('module %s has not attribute __file__' % name)
    return os.path.dirname(os.path.abspath(path))
alice_path = get_module_dir('aiml') + '/botdata/alice'
#切换到语料库所在工作目录
os.chdir(alice_path)
alice = aiml.Kernel()
alice.learn("startup.xml")
alice.respond('LOAD ALICE')
while True:
	print( alice.respond(input("Enter your message >> ")))

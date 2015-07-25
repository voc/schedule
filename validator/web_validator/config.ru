root_dir = File.dirname(__FILE__)
app_file = File.join(root_dir, 'webapp.rb')
require app_file

set :root,        root_dir
set :app_file,    app_file
disable :run

run Sinatra::Application

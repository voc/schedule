# encoding: utf-8
require 'sinatra'
require 'haml'
require 'nokogiri'
require 'net/http'

XSD_URL = "https://raw.githubusercontent.com/voc/schedule/master/validator/"\
          "xsd/schedule.xml.xsd"

set :xsd do
  uri  = URI.parse(XSD_URL)
  http = Net::HTTP.new(uri.host, uri.port)
  http.use_ssl = true
  request = Net::HTTP::Get.new(uri.request_uri)
  response = http.request(request)

  Nokogiri::XML::Schema(response.body)
end

error 400..510 do
  'Boom'
end

get '/' do
  haml :index
end

post '/validate' do
  if params[:schedulexml] =~ /\Ahttp/
    params[:schedulexml] = get_schedule(params[:schedulexml])
  end

  @errors = validate_xml(params[:schedulexml], settings.xsd)

  haml :index
end

helpers do
  def get_schedule(url)
    uri  = URI.parse(url)
    http = Net::HTTP.new(uri.host, uri.port)
    if uri.scheme == 'https'
      http.use_ssl = true
    end
    request = Net::HTTP::Get.new(uri.request_uri)
    response = http.request(request)

    response.body
  end

  def validate_xml(xml, xsd)
    doc = Nokogiri::XML(xml)

    errors = []
    xsd.validate(doc).each do |error|
      errors << error.message
    end

    errors
  end
end

import scrapy


class JobItem(scrapy.Item):
    url           = scrapy.Field()
    reference     = scrapy.Field()
    title         = scrapy.Field()
    lab           = scrapy.Field()
    location      = scrapy.Field()
    department    = scrapy.Field()
    contract_label= scrapy.Field()
    contract_type = scrapy.Field()
    duration      = scrapy.Field()
    degree        = scrapy.Field()
    is_new        = scrapy.Field()
    published_ago = scrapy.Field()
    match_reasons = scrapy.Field()


class DetailItem(scrapy.Item):
    url              = scrapy.Field()
    reference        = scrapy.Field()
    title            = scrapy.Field()
    lab              = scrapy.Field()
    location         = scrapy.Field()
    department       = scrapy.Field()
    contract_label   = scrapy.Field()
    
    description      = scrapy.Field()
    missions         = scrapy.Field()
    activities       = scrapy.Field()
    profile          = scrapy.Field()
    work_environment = scrapy.Field()
    
    salary           = scrapy.Field()
    deadline         = scrapy.Field()
    start_date       = scrapy.Field()
    work_time        = scrapy.Field()
    activity_sector  = scrapy.Field()
    job_type         = scrapy.Field()
    disability_access= scrapy.Field()

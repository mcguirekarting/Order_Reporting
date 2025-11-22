def query_order_api(from_date, to_date, report_config=None):
    """
    Query the order search API with configurable parameters and log response to MongoDB
    
    Args:
        from_date (str): Start date in format "DD MMM YYYY"
        to_date (str): End date in format "DD MMM YYYY"
        report_config (dict, optional): Report configuration with query parameters
        
    Returns:
        list: Order data results
    """
    # Import the MongoDB utilities - put this inside the function to avoid
    # import errors if mongo_utils isn't available
    try:
        from utils.mongo_utils import log_api_response
        mongo_available = True
    except ImportError:
        logger.warning("MongoDB utilities not available. API responses will not be logged.")
        mongo_available = False
    
    # Get API configuration
    api_base_url = Variable.get("order_api_base_url")
    search_endpoint = f"{api_base_url}/order/search"
    
    # Get token for authentication
    token = get_api_auth_token()
    
    # Build default search payload
    payload = {
        "ViewName": "orderdetails",
        "Filters": [
            {
                "ViewName": "orderdetails",
                "AttributeId": "OrderDate",
                "DataType": None,
                "requiredFilter": False,
                "FilterValues": [
                    {
                        "filter": {
                            "date": {
                                "from": from_date,
                                "to": to_date
                            },
                            "time": {
                                "from": "00:00",
                                "to": "23:59",
                                "start": 0,
                                "end": 288
                            },
                            "quickSelect": "CUSTOM"
                        }
                    }
                ],
                "negativeFilter": False
            }
        ],
        "RequestAttributeIds": [],
        "SearchOptions": [],
        "SearchChains": [],
        "FilterExpression": None,
        "Page": 0,
        "TotalCount": -1,
        "SortOrder": "desc",
        "SortIndicator": "chevron-up",
        "TimeZone": "America/Chicago",
        "IsCommonUI": False,
        "ComponentShortName": None,
        "EnableMaxCountLimit": True,
        "MaxCountLimit": 1000,
        "ComponentName": "com-manh-cp-xint",
        "Size": 100,
        "Sort": "OrderDate"
    }
    
    # Customize payload based on report configuration
    if report_config:
        # Set request fields if specified
        if "report_fields" in report_config:
            payload["RequestAttributeIds"] = report_config["report_fields"]
            
        # Set view name if specified
        view_name = report_config.get("query_parameters", {}).get("view_name")
        if view_name:
            payload["ViewName"] = view_name
            payload["Filters"][0]["ViewName"] = view_name
            
        # Set sort field if specified
        sort_field = report_config.get("query_parameters", {}).get("sort_field")
        if sort_field:
            payload["Sort"] = sort_field
            
        # Add order type filter if specified
        order_type = report_config.get("query_parameters", {}).get("order_type")
        if order_type:
            payload["Filters"].append({
                "ViewName": payload["ViewName"],
                "AttributeId": "TextSearch",
                "DataType": "text",
                "requiredFilter": False,
                "FilterValues": [
                    f"\"{order_type}\""
                ],
                "negativeFilter": False
            })
    
    # Set headers with authentication
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    all_results = []
    page = 0
    
    try:
        while True:
            payload["Page"] = page
            logger.info(f"Searching page {page}...")
            
            response = requests.post(
                search_endpoint, 
                json=payload,
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error in API call: {response.status_code} - {response.text}")
                raise Exception(f"API returned error: {response.status_code}")
            
            result_data = response.json()
            
            # Check if we have results
            if not result_data.get("data") or len(result_data["data"]) == 0:
                logger.info(f"No more results found after page {page}")
                break
            
            all_results.extend(result_data["data"])
            logger.info(f"Retrieved {len(result_data['data'])} records from page {page}")
            
            # Check if we've reached the end
            if len(all_results) >= result_data.get("totalCount", 0) or len(result_data["data"]) < payload["Size"]:
                break
            
            page += 1
    
    except Exception as e:
        logger.error(f"Error during API search: {str(e)}")
        raise
    
    logger.info(f"Total records retrieved: {len(all_results)}")
    
    # Log the API response to MongoDB if available
    if mongo_available:
        try:
            report_id = report_config.get("report_id") if report_config else None
            query_params = {
                "from_date": from_date,
                "to_date": to_date,
                "report_config": {
                    "report_id": report_id,
                    "view_name": payload.get("ViewName"),
                    "sort_field": payload.get("Sort"),
                    "filters": payload.get("Filters")
                }
            }
            
            # Log to MongoDB and get the MongoDB document ID
            mongo_doc_id = log_api_response(all_results, report_id, query_params)
            if mongo_doc_id:
                logger.info(f"API response logged to MongoDB with ID: {mongo_doc_id}")
                
                # Store the MongoDB document ID in a Variable for potential reuse
                if report_id:
                    Variable.set(f"last_response_{report_id}", mongo_doc_id)
            else:
                logger.warning("Failed to log API response to MongoDB")
        except Exception as e:
            logger.error(f"Error logging API response to MongoDB: {str(e)}")
            # Continue execution even if MongoDB logging fails
    
    return all_results
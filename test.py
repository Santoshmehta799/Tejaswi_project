import json
from collections import defaultdict

# Your JSON data
data = [{"product_number": "A10JE01", "quality": "Premium", "colour": "White", "product_type": "Roll", "weight": 12.0}, {"product_number": "A10JE02", "quality": "Premium", "colour": "White", "product_type": "Roll", "weight": 12.0}, {"product_number": "A10JE03", "quality": "Premium", "colour": "White", "product_type": "Roll", "weight": 21.0}, {"product_number": "A10JE04", "quality": "Premium", "colour": "White", "product_type": "Patti", "weight": 211.0}, {"product_number": "A10JE05", "quality": "Premium", "colour": "White", "product_type": "Patti", "weight": 14.0}, {"product_number": "A10JE06", "quality": "Standard", "colour": "White", "product_type": "Roll", "weight": 88.0}, {"product_number": "A10JE07", "quality": "Standard", "colour": "White", "product_type": "Roll", "weight": 25.0}, {"product_number": "A10JE08", "quality": "Economy", "colour": "Blue", "product_type": "Roll", "weight": 12.0}, {"product_number": "A10JE10", "quality": "Economy", "colour": "Blue", "product_type": "Roll", "weight": 45.0}, {"product_number": "A10JE104", "quality": "Economy", "colour": "Blue", "product_type": "Roll", "weight": 45.0}, {"product_number": "A10JE124", "quality": "Premium", "colour": "Green", "product_type": "Roll", "weight": 5.0}, {"product_number": "A10JE446", "quality": "Premium", "colour": "Green", "product_type": "Patti", "weight": 45.0}]

def group_and_summarize_data(data):
    # Create nested structure: color -> quality -> product_type
    grouped = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    
    # Group the data
    for item in data:
        color = item['colour']
        quality = item['quality']
        product_type = item['product_type']
        
        grouped[color][quality][product_type].append(item)
    
    # Create the hierarchical output structure
    result = {}
    
    for color, qualities in grouped.items():
        result[color] = {}
        
        for quality, product_types in qualities.items():
            result[color][quality] = {}
            
            for product_type, items in product_types.items():
                # Calculate totals for this product type
                total_weight = sum(item['weight'] for item in items)
                count = len(items)
                
                result[color][quality][product_type] = {
                    'pieces': count,
                    'total_weight_kg': round(total_weight, 2),
                    'items': items  # Include individual items if needed
                }
    
    return result

def format_output_like_image2(grouped_data):
    """Format the output similar to image 2 structure"""
    formatted_output = {}
    
    for color, qualities in grouped_data.items():
        formatted_output[color] = {}
        
        for quality, product_types in qualities.items():
            formatted_output[color][quality] = []
            
            for product_type, summary in product_types.items():
                formatted_output[color][quality].append({
                    'type': product_type,
                    'pieces': summary['pieces'],
                    'total_weight_kg': summary['total_weight_kg']
                })
    
    return formatted_output

def print_formatted_output(data):
    """Print in a format similar to image 2"""
    for color, qualities in data.items():
        print(f"\n{color.upper()}")
        print("=" * 40)
        
        for quality, product_types in qualities.items():
            print(f"\n{quality}")
            print("-" * 20)
            
            for item in product_types:
                print(f"• {item['type']} — {item['pieces']} pcs | {item['total_weight_kg']} kg")

# Process the data
grouped_result = group_and_summarize_data(data)
formatted_result = format_output_like_image2(grouped_result)

# Print the results
print("HIERARCHICAL GROUPING RESULTS:")
print_formatted_output(formatted_result)

print("\n" + "="*50)
print("JSON OUTPUT:")
print("="*50)
print(json.dumps(formatted_result, indent=2))

# Alternative: More detailed output with individual items
print("\n" + "="*50)
print("DETAILED JSON OUTPUT (with individual items):")
print("="*50)
print(json.dumps(grouped_result, indent=2))
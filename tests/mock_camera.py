"""
Mock Camera for SITL Testing
Generates synthetic pineapple field images for testing without actual hardware

Usage:
    camera = ImageCapture()
    img_path = camera.capture(prefix="test")
    camera.close()
"""

import os
from datetime import datetime
import logging
import pathlib
from PIL import Image, ImageDraw, ImageFont
import random

logger = logging.getLogger("MockCamera")


class MockImageCapture:
    """
    Simulated camera for SITL testing
    Generates synthetic images that look like pineapple field captures
    """
    
    def __init__(self, output_dir=None, keep_preview=False):
        """
        Initialize mock camera
        
        Args:
            output_dir: Directory to save images (default: from config_sitl)
            keep_preview: Ignored (for compatibility with real camera)
        """
        if output_dir is None:
            try:
                import config_sitl as config
                output_dir = str(config.IMAGE_DIR)
            except ImportError:
                output_dir = "./images_sitl"
        
        self.output_dir = pathlib.Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.capture_count = 0
        
        logger.info(f"Mock camera initialized (SITL mode)")
        logger.info(f"Output directory: {self.output_dir}")

    def capture(self, prefix="img"):
        """
        Generate a synthetic test image
        
        Args:
            prefix: Filename prefix (e.g., "wp1" for waypoint 1)
            
        Returns:
            str: Full path to generated image
        """
        # Generate timestamp
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")[:-3]
        filename = f"{prefix}_{ts}.jpg"
        fullpath = self.output_dir / filename
        
        # Generate synthetic pineapple field image
        self._generate_pineapple_image(fullpath, prefix)
        
        self.capture_count += 1
        logger.info(f"Mock capture #{self.capture_count}: {fullpath}")
        
        return str(fullpath)
    
    def _generate_pineapple_image(self, filepath, prefix):
        """
        Create a realistic-looking synthetic pineapple field image
        
        Args:
            filepath: Where to save the image
            prefix: Image prefix (used for overlay text)
        """
        # Image size (reduced from 4056x3040 for faster generation)
        width, height = 1920, 1440
        
        # Simulated field conditions (changes each capture)
        field_conditions = [
            {
                'name': 'Healthy Field',
                'bg_color': (45, 155, 65),      # Vibrant green
                'fruit_color': (220, 180, 40),  # Golden yellow
                'crown_color': (60, 180, 80),   # Bright green
                'defect_chance': 0.1
            },
            {
                'name': 'Diseased Field',
                'bg_color': (90, 110, 70),      # Dull green
                'fruit_color': (160, 140, 60),  # Brownish yellow
                'crown_color': (80, 100, 60),   # Dull green
                'defect_chance': 0.6
            },
            {
                'name': 'Mixed Condition',
                'bg_color': (60, 140, 75),      # Medium green
                'fruit_color': (200, 170, 50),  # Yellow
                'crown_color': (70, 160, 75),   # Green
                'defect_chance': 0.3
            }
        ]
        
        # Select random field condition
        condition = random.choice(field_conditions)
        
        # Create base image with soil/ground texture
        img = Image.new('RGB', (width, height), condition['bg_color'])
        draw = ImageDraw.Draw(img)
        
        # Add ground texture (dirt/soil appearance)
        for _ in range(5000):
            x = random.randint(0, width)
            y = random.randint(0, height)
            color_var = random.randint(-20, 20)
            pixel_color = tuple(max(0, min(255, c + color_var)) for c in condition['bg_color'])
            draw.point((x, y), fill=pixel_color)
        
        # Add pineapple plants (3-8 per image)
        num_plants = random.randint(3, 8)
        
        for plant_idx in range(num_plants):
            # Random position
            x = random.randint(150, width - 150)
            y = random.randint(150, height - 150)
            
            # Random size (simulate different distances/perspectives)
            base_size = random.randint(60, 150)
            
            # Decide if this plant is diseased
            is_diseased = random.random() < condition['defect_chance']
            
            # Draw pineapple fruit (oval body)
            if is_diseased:
                # Diseased appearance (darker, brownish)
                fruit_color = (
                    condition['fruit_color'][0] - 40,
                    condition['fruit_color'][1] - 40,
                    condition['fruit_color'][2] + 20
                )
                # Add disease spots
                for _ in range(random.randint(3, 8)):
                    spot_x = x + random.randint(-base_size//2, base_size//2)
                    spot_y = y + random.randint(-base_size//2, base_size//2)
                    spot_size = random.randint(5, 15)
                    draw.ellipse(
                        [spot_x-spot_size, spot_y-spot_size, 
                         spot_x+spot_size, spot_y+spot_size],
                        fill=(80, 60, 40)  # Brown spots
                    )
            else:
                fruit_color = condition['fruit_color']
            
            # Draw pineapple body
            draw.ellipse(
                [x - base_size, y - base_size, 
                 x + base_size, y + base_size],
                fill=fruit_color,
                outline=(fruit_color[0]-30, fruit_color[1]-30, fruit_color[2]-30),
                width=3
            )
            
            # Draw diamond pattern (pineapple texture)
            for dx in range(-base_size, base_size, 20):
                for dy in range(-base_size, base_size, 20):
                    if (dx**2 + dy**2) < base_size**2:  # Only inside the oval
                        draw.line(
                            [(x+dx-5, y+dy), (x+dx+5, y+dy)],
                            fill=(fruit_color[0]-20, fruit_color[1]-20, fruit_color[2]-20),
                            width=2
                        )
            
            # Draw crown (leaves on top)
            crown_color = condition['crown_color'] if not is_diseased else (
                condition['crown_color'][0] - 30,
                condition['crown_color'][1] - 30,
                condition['crown_color'][2]
            )
            
            # Multiple leaves
            for leaf_angle in range(0, 360, 45):
                leaf_length = base_size * 0.8
                import math
                rad = math.radians(leaf_angle)
                leaf_x = x + int(leaf_length * math.cos(rad))
                leaf_y = y - base_size + int(leaf_length * math.sin(rad))
                
                # Draw leaf as a line
                draw.line(
                    [(x, y - base_size), (leaf_x, leaf_y)],
                    fill=crown_color,
                    width=8
                )
        
        # Add metadata overlay
        try:
            # Try to load a nice font
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            # Fallback to default font
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        # Create overlay information
        text_info = [
            ("SITL SIMULATION", font_large, (255, 255, 0)),
            (f"Waypoint: {prefix}", font_small, (255, 255, 255)),
            (f"Field: {condition['name']}", font_small, (255, 255, 255)),
            (f"Time: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}", font_small, (200, 200, 200)),
            (f"Image #{self.capture_count + 1}", font_small, (200, 200, 200))
        ]
        
        # Draw semi-transparent background for text
        overlay_height = 160
        overlay = Image.new('RGBA', (width, overlay_height), (0, 0, 0, 180))
        overlay_draw = ImageDraw.Draw(overlay)
        
        # Draw text on overlay
        text_y = 10
        for text, font, color in text_info:
            overlay_draw.text((15, text_y), text, fill=color, font=font)
            text_y += 30
        
        # Composite overlay onto main image
        img.paste(overlay, (0, 0), overlay)
        
        # Add corner indicators (simulate camera metadata)
        corner_font = ImageFont.load_default()
        draw.text((width - 200, height - 30), 
                 f"Mock Cam v1.0", 
                 fill=(150, 150, 150), 
                 font=corner_font)
        
        # Save image with high quality
        img.save(filepath, quality=95, optimize=True)
        
        logger.debug(f"Generated {width}x{height} synthetic image: {filepath}")
        logger.debug(f"Condition: {condition['name']}, Plants: {num_plants}")
    
    def close(self):
        """
        Cleanup camera resources
        No actual hardware to close, but maintains API compatibility
        """
        logger.info(f"Mock camera closed.")
        logger.info(f"Total synthetic images generated: {self.capture_count}")


# Alias for drop-in replacement compatibility
ImageCapture = MockImageCapture


# Self-test functionality
if __name__ == "__main__":
    """
    Test the mock camera by generating sample images
    Run: python3 mock_camera.py
    """
    print("="*60)
    print("Mock Camera Self-Test")
    print("="*60)
    
    # Create test directory
    test_dir = pathlib.Path("./test_images")
    test_dir.mkdir(exist_ok=True)
    
    # Initialize camera
    camera = MockImageCapture(output_dir=str(test_dir))
    
    # Generate test images
    print("\nGenerating 5 test images...")
    for i in range(5):
        img_path = camera.capture(prefix=f"test_wp{i}")
        print(f"  ✓ Created: {img_path}")
    
    # Close camera
    camera.close()
    
    print(f"\n✓ Test complete! Check images in: {test_dir}")
    print("="*60)
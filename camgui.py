#!/usr/bin/env python3
"""
Simple GUI Camera App for Raspberry Pi Camera Module v3
"""

import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from picamera2 import Picamera2
from libcamera import controls
from datetime import datetime
import threading
import time

class CameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PinyaSuri Camera")
        self.root.geometry("900x700")
        self.root.configure(bg='#2c3e50')
        
        # Initialize camera
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (4608, 2592)},  # Full res for capture
            lores={"size": (640, 480)},    # Preview resolution
            display="lores"
        )
        self.picam2.configure(config)
        self.picam2.set_controls({"AfMode": controls.AfModeEnum.Continuous})
        self.picam2.start()
        
        # Variables
        self.running = True
        self.image_count = 0
        
        # Create GUI
        self.create_widgets()
        
        # Start preview update
        self.update_preview()
        
    def create_widgets(self):
        # Title
        title = tk.Label(
            self.root, 
            text="📷 PinyaSuri Camera", 
            font=('Arial', 24, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title.pack(pady=10)
        
        # Preview frame
        preview_frame = tk.Frame(self.root, bg='#34495e', relief=tk.SUNKEN, borderwidth=3)
        preview_frame.pack(pady=10, padx=20)
        
        self.preview_label = tk.Label(preview_frame, bg='black')
        self.preview_label.pack()
        
        # Status label
        self.status_label = tk.Label(
            self.root,
            text="Camera Ready",
            font=('Arial', 12),
            bg='#2c3e50',
            fg='#2ecc71'
        )
        self.status_label.pack(pady=10)
        
        # Buttons frame
        btn_frame = tk.Frame(self.root, bg='#2c3e50')
        btn_frame.pack(pady=20)
        
        # Capture button
        self.capture_btn = tk.Button(
            btn_frame,
            text="📸 CAPTURE IMAGE",
            command=self.capture_image,
            font=('Arial', 16, 'bold'),
            bg='#27ae60',
            fg='white',
            activebackground='#229954',
            activeforeground='white',
            width=20,
            height=2,
            cursor='hand2',
            relief=tk.RAISED,
            borderwidth=3
        )
        self.capture_btn.pack(side=tk.LEFT, padx=10)
        
        # Exit button
        exit_btn = tk.Button(
            btn_frame,
            text="❌ EXIT",
            command=self.close_app,
            font=('Arial', 16, 'bold'),
            bg='#c0392b',
            fg='white',
            activebackground='#a93226',
            activeforeground='white',
            width=12,
            height=2,
            cursor='hand2',
            relief=tk.RAISED,
            borderwidth=3
        )
        exit_btn.pack(side=tk.LEFT, padx=10)
        
        # Image counter
        self.counter_label = tk.Label(
            self.root,
            text="Images captured: 0",
            font=('Arial', 11),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.counter_label.pack(pady=5)
        
    def update_preview(self):
        if self.running:
            try:
                # Capture array for preview
                array = self.picam2.capture_array("lores")
                
                # Convert to PIL Image
                image = Image.fromarray(array)
                
                # Convert to PhotoImage
                photo = ImageTk.PhotoImage(image)
                
                # Update label
                self.preview_label.config(image=photo)
                self.preview_label.image = photo
                
            except Exception as e:
                print(f"Preview error: {e}")
            
            # Schedule next update
            self.root.after(30, self.update_preview)
    
    def capture_image(self):
        # Disable button temporarily
        self.capture_btn.config(state='disabled', bg='#7f8c8d')
        self.status_label.config(text="Capturing...", fg='#f39c12')
        
        def capture_thread():
            try:
                # Generate filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"image_{timestamp}.jpg"
                
                # Capture full resolution image
                self.picam2.capture_file(filename)
                
                # Update counter
                self.image_count += 1
                
                # Update UI
                self.root.after(0, lambda: self.status_label.config(
                    text=f"✓ Saved: {filename}", 
                    fg='#2ecc71'
                ))
                self.root.after(0, lambda: self.counter_label.config(
                    text=f"Images captured: {self.image_count}"
                ))
                
                # Flash effect
                self.root.after(0, lambda: self.preview_label.config(bg='white'))
                time.sleep(0.1)
                self.root.after(0, lambda: self.preview_label.config(bg='black'))
                
                print(f"Image saved: {filename}")
                
            except Exception as e:
                self.root.after(0, lambda: self.status_label.config(
                    text=f"Error: {str(e)}", 
                    fg='#e74c3c'
                ))
                print(f"Capture error: {e}")
            
            finally:
                # Re-enable button
                time.sleep(0.5)
                self.root.after(0, lambda: self.capture_btn.config(
                    state='normal', 
                    bg='#27ae60'
                ))
                self.root.after(0, lambda: self.status_label.config(
                    text="Camera Ready", 
                    fg='#2ecc71'
                ))
        
        # Run capture in separate thread
        threading.Thread(target=capture_thread, daemon=True).start()
    
    def close_app(self):
        self.running = False
        self.picam2.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.protocol("WM_DELETE_WINDOW", app.close_app)
    root.mainloop()
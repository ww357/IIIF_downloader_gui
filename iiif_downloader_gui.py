#!/usr/bin/env python3
"""
IIIF Image Downloader GUI with Full-Resolution Tiling
-----------------------------------------------------
Downloads IIIF images at full resolution by stitching together server-native tiles.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
from PIL import Image
import io
import os
import threading
import math
import json
import re
import sys
from typing import Dict, Tuple, List, Optional

class IIIFDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("IIIF Image Downloader - Full Resolution")
        self.root.geometry("600x550")
        self.root.resizable(True, True)
        
        # Create main frame with notebook for tabs
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Download Tab
        self.download_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.download_frame, text="Download")
        self.setup_download_tab()
        
        # Log Tab
        self.log_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.log_frame, text="Log")
        self.setup_log_tab()
        
        # Variables
        self.is_downloading = False
        self.cancel_flag = False
        
        # Set default download directory
        self.set_default_destination()
        
        # Console output redirect
        sys.stdout = TextRedirector(self.log_text, "stdout")
        sys.stderr = TextRedirector(self.log_text, "stderr")
    
    def setup_download_tab(self):
        """Setup the download tab interface"""
        main_frame = ttk.Frame(self.download_frame, padding="15")
        main_frame.pack(fill='both', expand=True)
        
        # Configure grid
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="IIIF Full Resolution Downloader", 
                               font=("Arial", 14, "bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 15))
        
        # URL Field
        ttk.Label(main_frame, text="IIIF URL:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.url_entry = ttk.Entry(main_frame, width=60)
        self.url_entry.grid(row=1, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Example label
        ttk.Label(main_frame, text="Example: https://map-view.nls.uk/iiif/2/12807%2F128076885", 
                 font=("Arial", 8)).grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(0, 15))
        
        # Target Destination
        ttk.Label(main_frame, text="Save To:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.dest_entry = ttk.Entry(main_frame, width=50)
        self.dest_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        self.browse_button = ttk.Button(main_frame, text="Browse", command=self.browse_directory)
        self.browse_button.grid(row=3, column=2, padx=(5, 0), pady=5)
        
        # File Name
        ttk.Label(main_frame, text="File Name:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.name_entry = ttk.Entry(main_frame, width=60)
        self.name_entry.insert(0, "downloaded_image")
        self.name_entry.grid(row=4, column=1, columnspan=2, sticky=(tk.W, tk.E), pady=5, padx=(5, 0))
        
        # Format Selection
        ttk.Label(main_frame, text="Format:").grid(row=5, column=0, sticky=tk.W, pady=10)
        self.format_var = tk.StringVar(value="tiff")
        format_frame = ttk.Frame(main_frame)
        format_frame.grid(row=5, column=1, columnspan=2, sticky=tk.W, pady=10)
        
        ttk.Radiobutton(format_frame, text="TIFF (Lossless)", variable=self.format_var, value="tiff").pack(side=tk.LEFT)
        ttk.Radiobutton(format_frame, text="PNG", variable=self.format_var, value="png").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Radiobutton(format_frame, text="JPEG", variable=self.format_var, value="jpg").pack(side=tk.LEFT, padx=(10, 0))
        
        # Tile Size Option
        ttk.Label(main_frame, text="Tile Size:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.tile_var = tk.StringVar(value="auto")
        tile_frame = ttk.Frame(main_frame)
        tile_frame.grid(row=6, column=1, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Radiobutton(tile_frame, text="Auto (Server Default)", variable=self.tile_var, value="auto").pack(side=tk.LEFT)
        ttk.Radiobutton(tile_frame, text="Custom:", variable=self.tile_var, value="custom").pack(side=tk.LEFT, padx=(10, 0))
        self.custom_tile_entry = ttk.Entry(tile_frame, width=8)
        self.custom_tile_entry.insert(0, "1024")
        self.custom_tile_entry.pack(side=tk.LEFT, padx=(5, 0))
        ttk.Label(tile_frame, text="px").pack(side=tk.LEFT, padx=(2, 0))
        
        # Workers Option
        ttk.Label(main_frame, text="Concurrent Downloads:").grid(row=7, column=0, sticky=tk.W, pady=10)
        self.workers_var = tk.IntVar(value="4")
        workers_frame = ttk.Frame(main_frame)
        workers_frame.grid(row=7, column=1, columnspan=2, sticky=tk.W, pady=10)
        
        ttk.Scale(workers_frame, from_=1, to=16, orient=tk.HORIZONTAL, 
                  variable=self.workers_var, length=150).pack(side=tk.LEFT)
        self.workers_label = ttk.Label(workers_frame, textvariable=self.workers_var)
        self.workers_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Control Buttons Frame
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=8, column=0, columnspan=3, pady=20)
        
        self.download_button = ttk.Button(button_frame, text="Download Image", 
                                         command=self.start_download, width=20)
        self.download_button.pack(side=tk.LEFT, padx=(0, 10))
        
        self.cancel_button = ttk.Button(button_frame, text="Cancel", 
                                       command=self.cancel_download, state='disabled', width=20)
        self.cancel_button.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='determinate')
        self.progress.grid(row=9, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=10)
        
        # Status label
        self.status_label = ttk.Label(main_frame, text="Ready")
        self.status_label.grid(row=10, column=0, columnspan=3, pady=5)
    
    def setup_log_tab(self):
        """Setup the log tab interface"""
        main_frame = ttk.Frame(self.log_frame, padding="10")
        main_frame.pack(fill='both', expand=True)
        
        # Log text widget
        self.log_text = scrolledtext.ScrolledText(main_frame, height=20, width=70)
        self.log_text.pack(fill='both', expand=True)
        
        # Clear log button
        clear_button = ttk.Button(main_frame, text="Clear Log", command=self.clear_log)
        clear_button.pack(pady=10)
    
    def clear_log(self):
        """Clear the log text"""
        self.log_text.delete(1.0, tk.END)
    
    def set_default_destination(self):
        """Set default download directory"""
        downloads_path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if os.path.exists(downloads_path):
            self.dest_entry.insert(0, downloads_path)
    
    def browse_directory(self):
        """Open directory browser"""
        directory = filedialog.askdirectory()
        if directory:
            self.dest_entry.delete(0, tk.END)
            self.dest_entry.insert(0, directory)
    
    def get_headers(self):
        """Get request headers to mimic a web browser"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }
    
    def normalize_url(self, url):
        """Normalize IIIF URL (from original script)"""
        url = re.split(r'[?#]', url)[0]
        if url.endswith('/info.json'):
            url = url[:-len('/info.json')]
        return url.rstrip('/')
    
    def fetch_info_json(self, service_url):
        """Fetch and parse info.json (from original script)"""
        info_url = f"{service_url}/info.json"
        headers = self.get_headers()
        r = requests.get(info_url, headers=headers, timeout=30)
        r.raise_for_status()
        return r.json()
    
    def get_tile_spec(self, info):
        """Get tile specification from server info (from original script)"""
        tiles = info.get('tiles') or []
        custom_tile = None if self.tile_var.get() == "auto" else int(self.custom_tile_entry.get())
        
        if tiles:
            # Choose the first tile spec with scaleFactor 1 if present, else the first.
            chosen = None
            for t in tiles:
                sfs = t.get('scaleFactors') or []
                if 1 in sfs:
                    chosen = t
                    break
            if chosen is None:
                chosen = tiles[0]
            tw = int(chosen.get('width') or chosen.get('tileWidth') or 512)
            th = int(chosen.get('height') or chosen.get('tileHeight') or tw)
            overlap = int(chosen.get('overlap') or 0)
            return tw, th, overlap
        
        # No tiles advertised: use custom or default
        if not custom_tile:
            custom_tile = 1024
        return custom_tile, custom_tile, 0
    
    def respect_max_area(self, info, tile_w, tile_h):
        """Respect server's maxArea limit (from original script)"""
        max_area = info.get('maxArea')
        if not max_area:
            return tile_w, tile_h
        area = tile_w * tile_h
        if area <= max_area:
            return tile_w, tile_h
        scale = math.sqrt(max_area / area)
        return max(1, int(tile_w * scale)), max(1, int(tile_h * scale))
    
    def build_region_urls(self, service_url, info, tile_w, tile_h):
        """Build URLs for all tile regions (from original script)"""
        width = int(info['width'])
        height = int(info['height'])
        
        # Use JPEG for tiles (most servers support it)
        ext = 'jpg'
        quality = 'default'
        
        urls = []
        y = 0
        while y < height:
            h = min(tile_h, height - y)
            x = 0
            while x < width:
                w = min(tile_w, width - x)
                region = f"{x},{y},{w},{h}"
                url = f"{service_url}/{region}/full/0/{quality}.{ext}"
                urls.append((url, (x, y, w, h)))
                x += tile_w
            y += tile_h
        return urls
    
    def download_one(self, session, url):
        """Download a single tile (from original script)"""
        r = session.get(url, headers=self.get_headers(), timeout=60)
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGBA")
    
    def start_download(self):
        """Start the download process"""
        if not self.validate_inputs():
            return
        
        if self.is_downloading:
            messagebox.showwarning("Already Downloading", "A download is already in progress.")
            return
        
        self.is_downloading = True
        self.cancel_flag = False
        
        # Disable/enable buttons
        self.download_button.config(state='disabled')
        self.cancel_button.config(state='normal')
        
        # Start download in separate thread
        thread = threading.Thread(target=self.download_image)
        thread.daemon = True
        thread.start()
    
    def cancel_download(self):
        """Cancel the current download"""
        self.cancel_flag = True
        self.status_label.config(text="Cancelling...")
    
    def validate_inputs(self):
        """Validate user inputs"""
        url = self.url_entry.get().strip()
        destination = self.dest_entry.get().strip()
        filename = self.name_entry.get().strip()
        
        if not url:
            messagebox.showerror("Error", "Please enter a IIIF URL")
            return False
        
        if not destination:
            messagebox.showerror("Error", "Please select a destination directory")
            return False
        
        if not filename:
            messagebox.showerror("Error", "Please enter a file name")
            return False
        
        # Check or create destination directory
        if not os.path.exists(destination):
            try:
                os.makedirs(destination)
            except:
                messagebox.showerror("Error", "Cannot create destination directory")
                return False
        
        # Validate custom tile size
        if self.tile_var.get() == "custom":
            try:
                tile_size = int(self.custom_tile_entry.get())
                if tile_size < 64 or tile_size > 4096:
                    messagebox.showerror("Error", "Tile size must be between 64 and 4096 pixels")
                    return False
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid number for tile size")
                return False
        
        return True
    
    def update_progress(self, value):
        """Update progress bar from any thread"""
        self.root.after(0, lambda: self.progress.config(value=value))
    
    def update_status(self, message):
        """Update status label from any thread"""
        self.root.after(0, lambda: self.status_label.config(text=message))
    
    def log_message(self, message):
        """Log message to log tab"""
        self.root.after(0, lambda: self.log_text.insert(tk.END, message + "\n"))
        self.root.after(0, lambda: self.log_text.see(tk.END))
    
    def download_image(self):
        """Main download function with full-resolution tiling"""
        try:
            # Get values from UI
            url = self.url_entry.get().strip()
            destination = self.dest_entry.get().strip()
            filename = self.name_entry.get().strip()
            file_format = self.format_var.get()
            workers = self.workers_var.get()
            
            # Normalize URL
            service_url = self.normalize_url(url)
            
            self.update_status("Getting image information...")
            self.log_message(f"Service URL: {service_url}")
            
            # Fetch image info
            info = self.fetch_info_json(service_url)
            
            width = int(info['width'])
            height = int(info['height'])
            
            self.update_status(f"Image size: {width} x {height} pixels")
            self.log_message(f"Image dimensions: {width} x {height}")
            
            # Get tile specification
            tile_w, tile_h, overlap = self.get_tile_spec(info)
            tile_w, tile_h = self.respect_max_area(info, tile_w, tile_h)
            
            self.log_message(f"Using tile size: {tile_w} x {tile_h} (overlap: {overlap}px)")
            
            if info.get('maxArea'):
                self.log_message(f"Respecting server maxArea: {info['maxArea']}")
            
            # Build all tile URLs
            self.update_status("Preparing download URLs...")
            urls = self.build_region_urls(service_url, info, tile_w, tile_h)
            
            self.log_message(f"Total tiles to download: {len(urls)}")
            self.update_status(f"Downloading {len(urls)} tiles...")
            
            # Create canvas for final image
            canvas = Image.new("RGBA", (width, height))
            
            # Download tiles with threading
            with requests.Session() as session:
                session.headers.update(self.get_headers())
                
                downloaded = 0
                total = len(urls)
                
                # Use ThreadPoolExecutor for concurrent downloads
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                    # Submit all download tasks
                    future_to_url = {executor.submit(self.download_one, session, u): (u, box) 
                                    for (u, box) in urls}
                    
                    # Process completed downloads
                    for future in concurrent.futures.as_completed(future_to_url):
                        if self.cancel_flag:
                            self.log_message("Download cancelled by user")
                            break
                        
                        url, (x, y, w, h) = future_to_url[future]
                        
                        try:
                            img = future.result()
                            
                            # Crop to exact dimensions if needed
                            if img.size != (w, h):
                                img = img.crop((0, 0, w, h))
                            
                            # Paste onto canvas
                            canvas.paste(img, (x, y), img)
                            
                            downloaded += 1
                            progress = (downloaded / total) * 100
                            
                            self.update_progress(progress)
                            self.update_status(f"Downloaded {downloaded}/{total} tiles")
                            
                            if downloaded % 25 == 0 or downloaded == total:
                                self.log_message(f"Progress: {downloaded}/{total} tiles ({progress:.1f}%)")
                            
                        except Exception as e:
                            self.log_message(f"Error downloading tile {url}: {str(e)}")
                            if downloaded == 0:  # If first tile fails, abort
                                raise
                
                if self.cancel_flag:
                    self.update_status("Download cancelled")
                    self.log_message("Download was cancelled")
                    return
            
            # Create output path
            file_extension = file_format
            if file_format == 'jpg':
                file_extension = 'jpg'
            output_path = os.path.join(destination, f"{filename}.{file_extension}")
            
            # Save final image
            self.update_status("Saving image...")
            self.log_message(f"Saving to: {output_path}")
            
            if file_format == 'jpg':
                # Convert to RGB and save as JPEG
                rgb_canvas = Image.new("RGB", canvas.size, (255, 255, 255))
                rgb_canvas.paste(canvas, mask=canvas.split()[3])
                rgb_canvas.save(output_path, 'JPEG', quality=95, optimize=True)
            elif file_format == 'png':
                canvas.save(output_path, 'PNG', optimize=True)
            else:  # tiff
                canvas.save(output_path, 'TIFF', compression='tiff_deflate')
            
            # Success
            self.update_status("Download complete!")
            self.update_progress(100)
            self.log_message(f"Successfully saved to: {output_path}")
            
            # Show success message
            self.root.after(0, lambda: messagebox.showinfo(
                "Success", 
                f"Image saved to:\n{output_path}\n\n"
                f"Size: {width} x {height} pixels\n"
                f"Tiles: {len(urls)}\n"
                f"Format: {file_format.upper()}"
            ))
            
        except Exception as e:
            self.log_message(f"ERROR: {str(e)}")
            self.update_status("Download failed")
            self.root.after(0, lambda: messagebox.showerror(
                "Download Failed", 
                f"Error: {str(e)}"
            ))
        finally:
            # Reset UI state
            self.is_downloading = False
            self.root.after(0, lambda: self.download_button.config(state='normal'))
            self.root.after(0, lambda: self.cancel_button.config(state='disabled'))
            if not self.cancel_flag:
                self.root.after(0, lambda: self.progress.config(value=0))


class TextRedirector:
    """Redirect console output to tkinter text widget"""
    def __init__(self, widget, tag="stdout"):
        self.widget = widget
        self.tag = tag
    
    def write(self, string):
        self.widget.insert(tk.END, string, (self.tag,))
        self.widget.see(tk.END)
    
    def flush(self):
        pass


def main():
    root = tk.Tk()
    app = IIIFDownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
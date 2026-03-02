import requests
from tkinter import *
from tkinter import Toplevel, Label, Button, messagebox, font
from PIL import Image, ImageTk
import random
import utils
import os
import subprocess

SERVER_REGISTER_URL = "http://127.0.0.1:5000/register"
SERVER_AUTH_URL = "http://127.0.0.1:5000/authenticate"
SERVER_RECOVER_URL = "http://127.0.0.1:5000/recover-password"
SERVER_RESET_URL = "http://127.0.0.1:5000/reset-graphical-password"

root = Tk()

selected_image = None
selected_grid_point = None

def reset_selection():
    global selected_image, selected_grid_point
    selected_image = None
    selected_grid_point = None
    messagebox.showinfo("Reset", "Selections have been reset!")

def send_data(action="register"):
    global selected_image, selected_grid_point
    username = username_entry.get().strip()

    if not username or not selected_image :
        messagebox.showinfo("System", "Please enter Username, and select at least one Image with a Grid Point")
        return

    data = {
        "username": username,
        "image": selected_image,
        "grid_point": list(selected_grid_point) 
    }

    try:
        url = SERVER_REGISTER_URL if action == "register" else SERVER_AUTH_URL
        response = requests.post(url, json=data)
        result = response.json()

        if result.get("status") == "success":
            messagebox.showinfo("System", result.get("message"))
            if action == "register":
                recovery_passphrase = result.get("recovery_passphrase")
                messagebox.showinfo("Recovery Phrase", f"Please save this recovery phrase: {recovery_passphrase}")
            username_entry.delete(0, END)
            reset_selection()
        else:
            messagebox.showerror("System", result.get("message"))

    except requests.exceptions.RequestException as e:
        messagebox.showerror("System", f"Error: {e}")



def open_modal(image_path):
    """Open grid selection for a single image and point."""
    global selected_image
    global selected_grid_point

    modal_window = Toplevel(root)
    modal_window.title("Select Grid Point")
    GRID_SIZE, CELL_SIZE = 10, 30
    modal_window.geometry(f"{GRID_SIZE * CELL_SIZE}x{GRID_SIZE * CELL_SIZE + 50}")

    im_name = os.path.splitext(os.path.basename(image_path))[0]

    def on_click(event):
        global selected_image
        global selected_grid_point
        row, col = event.y // CELL_SIZE, event.x // CELL_SIZE
        selected_image = im_name
        selected_grid_point = (row,col)
        modal_window.destroy()
        messagebox.showinfo("Selected", f"Image: {im_name}\nGrid: Row {row}, Col {col}")

    image = Image.open(image_path).resize((GRID_SIZE * CELL_SIZE, GRID_SIZE * CELL_SIZE))
    tk_image = ImageTk.PhotoImage(image)

    canvas = Canvas(modal_window, width=image.width, height=image.height)
    canvas.pack()
    canvas.create_image(0, 0, anchor=NW, image=tk_image)
    canvas.image = tk_image

    for i in range(GRID_SIZE + 1):
        canvas.create_line(i * CELL_SIZE, 0, i * CELL_SIZE, GRID_SIZE * CELL_SIZE, fill="red")
        canvas.create_line(0, i * CELL_SIZE, GRID_SIZE * CELL_SIZE, i * CELL_SIZE, fill="red")

    canvas.bind("<Button-1>", on_click)
    Button(modal_window, text="Close", command=modal_window.destroy).pack(pady=10)


def open_forgot_password_window():
    """Open Forgot Password window to enter recovery word."""
    forgot_window = Toplevel(root)
    forgot_window.title("Forgot Password")
    forgot_window.geometry("400x400")

    Label(forgot_window, text="Enter Username:").pack()
    username_entry_fp = Entry(forgot_window, width=40)
    username_entry_fp.pack()

    Label(forgot_window, text="Enter Recovery Phrase:").pack()
    recovery_entry = Entry(forgot_window, width=40)
    recovery_entry.pack()

    def verify_recovery():
        data = {
            "username": username_entry_fp.get().strip(),
            "recovery_passphrase": recovery_entry.get().strip()
        }
        try:
            response = requests.post(SERVER_RECOVER_URL, json=data)
            result = response.json()
            if result["status"] == "success":
                messagebox.showinfo("Success", "Recovery verified. Please reset your graphical password.")
                user_id = result["user_id"]
                open_reset_password_window(user_id)
                forgot_window.destroy()
            else:
                messagebox.showerror("Error", result["message"])
        except requests.exceptions.RequestException as e:
            messagebox.showerror("System", f"Error: {e}")

    Button(forgot_window, text="Verify & Reset", command=verify_recovery).pack(pady=20)


def open_reset_password_window(user_id):
    """Open window to reset graphical password after recovery."""
    reset_window = Toplevel(root)
    reset_window.title("Reset Graphical Password")
    reset_window.geometry("400x200")

    Label(reset_window, text="Select New Image and Grid Point").pack()

    def finalize_reset():
        if not selected_image or not selected_grid_point:
            messagebox.showerror("Error", "Please select an image and a grid point first.")
            return

        data = {
            "user_id": user_id,
            "new_image": selected_image,
            "new_grid_points": [selected_grid_point]
        }
        try:
            response = requests.post(SERVER_RESET_URL, json=data)
            result = response.json()
            messagebox.showinfo("Success", f"{result['message']}")
            reset_window.destroy()
        except requests.exceptions.RequestException as e:
            messagebox.showerror("System", f"Error: {e}")

    Button(reset_window, text="Confirm Reset", command=finalize_reset).pack(pady=20)


# ---------- GUI Layout ----------
root.geometry("1280x600")
root.title("Graphical Password System")
root.resizable(False, False)

left_frame = Frame(root, background="#6A9C89")
left_frame.place(x=0, y=0, width=640, height=600)
right_frame = Frame(root, background="#C1D8C3")
right_frame.place(x=640, y=0, width=640, height=600)

title_font = font.Font(family="Microsoft YaHei UI Light", size=20, weight="bold")
label_font = font.Font(family="Microsoft YaHei UI Light", size=12, weight="bold")

Label(right_frame, text="Graphical Password System", font=title_font, bg="#C1D8C3").place(x=150, y=50)
Label(right_frame, text="Username:", font=label_font, bg="#C1D8C3").place(x=200, y=130)
username_entry = Entry(right_frame, font=label_font, width=30)
username_entry.place(x=200, y=160)

Button(right_frame, text="Register", font=label_font, bg="#6A9C89", fg="white", width=20, height=2,
       command=lambda: send_data("register")).place(x=230, y=250)
Button(right_frame, text="Login", font=label_font, bg="#6A9C89", fg="white", width=20, height=2,
       command=lambda: send_data("login")).place(x=230, y=320)
Button(right_frame, text="Reset Selections", font=label_font, bg="#FF7F7F", fg="white", width=20, height=1,
       command=reset_selection).place(x=230, y=390)
Button(right_frame, text="Forgot Password?", font=label_font, bg="#FFA500", fg="white", width=20, height=1,
       command=open_forgot_password_window).place(x=230, y=450)


# ---------- Load and Display Images ----------
imgList = utils.getCredentialImages()
random.shuffle(imgList)


def create_image_canvas(row, col, img_path):
    img_width, img_height = 640 // 3, 600 // 2
    canvas = Canvas(left_frame, width=img_width, height=img_height)
    canvas.bind("<Button-1>", lambda event: open_modal(img_path))
    canvas.place(x=col * img_width, y=row * img_height)
    img = Image.open(img_path).resize((img_width, img_height), Image.Resampling.LANCZOS)
    tk_img = ImageTk.PhotoImage(img)
    canvas.create_image(0, 0, anchor="nw", image=tk_img)
    canvas.image = tk_img


for i in range(2):
    for j in range(3):
        create_image_canvas(i, j, "credentialImages/" + imgList[i * 3 + j])

root.mainloop()

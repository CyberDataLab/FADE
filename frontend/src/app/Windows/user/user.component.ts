import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, FormsModule, ReactiveFormsModule } from '@angular/forms';
import { AuthenticationService } from '../../Authentication/authentication.service';
import { Password } from '../../DTOs/Password';

@Component({
  selector: 'app-user',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    FormsModule
  ],
  templateUrl: './user.component.html',
  styleUrls: ['./user.component.css']
})
export class UserComponent implements OnInit {
  user: any;
  isEditing = false;
  isChangingPassword = false;
  userForm: FormGroup;

  isPasswordModalOpen = false;

  passwordDTO: Password = {
    current_password: '',
    new_password: '',
    confirm_password: ''
  };

  current_passwordError: boolean;
  passwordError: boolean;
  confirm_passwordError: boolean;

  badPasswordError: boolean;
  badConfirmPasswordError: boolean;
  
  showCurrentPassword: boolean;
  showNewPassword: boolean;
  showConfirmPassword: boolean;

  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;

  constructor(
    private authService: AuthenticationService,
    private fb: FormBuilder
  ) {
    this.userForm = this.fb.group({
      username: [''],
      first_name: [''],
      last_name: [''],
      email: ['']
    });
    this.current_passwordError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;

    this.showCurrentPassword = false;
    this.showNewPassword = false;
    this.showConfirmPassword = false;
  }

  ngOnInit(): void {
    this.authService.getInfoActualUser().subscribe(data => {
      this.user = data;
      this.userForm.patchValue({
        username: this.user.username,
        first_name: this.user.first_name,
        last_name: this.user.last_name,
        email: this.user.email
      });
    });
  }

  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.changePassword();
    }
  }

  toggleVisibility(field: 'current' | 'new' | 'confirm'): void {
    if (field === 'current') this.showCurrentPassword = !this.showCurrentPassword;
    if (field === 'new') this.showNewPassword = !this.showNewPassword;
    if (field === 'confirm') this.showConfirmPassword = !this.showConfirmPassword;
  }

  enableEdit(): void {
    this.isEditing = true;
  }

  cancelEdit(): void {
    this.isEditing = false;
  }

  saveChanges(): void {
    const updatedUser = this.userForm.value;
    this.authService.updateUser(updatedUser).subscribe(() => {
      this.authService.getInfoActualUser().subscribe(data => {
        this.user = data;
        this.isEditing = false;
        alert('User information updated successfully');
      });
    });
  }

  enableChangePassword(): void {
    this.isChangingPassword = true;
  }
  
  cancelChangePassword(): void {
    this.isChangingPassword = false;
    this.passwordDTO = { current_password: '', new_password: '', confirm_password: '' };
  }

  changePassword(): void {
    this.current_passwordError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;

    if (this.passwordDTO.current_password === '') {
      this.current_passwordError = true;
    }

    if (this.passwordDTO.new_password === '') {
      this.passwordError = true; 
    } else if (!this.passwordPattern.test(this.passwordDTO.new_password)) {
      this.badPasswordError = true;
    }

    if (this.passwordDTO.confirm_password === '') {
      this.confirm_passwordError = true; 
    } else if (!this.passwordPattern.test(this.passwordDTO.confirm_password)) {
      this.badConfirmPasswordError = true;
    }

    if (
      this.passwordDTO.current_password !== '' &&
      this.passwordDTO.new_password !== '' &&
      this.passwordDTO.confirm_password !== '' &&
      !this.current_passwordError &&
      !this.badPasswordError &&
      !this.badConfirmPasswordError
    ) {
      if (this.passwordDTO.new_password != this.passwordDTO.confirm_password) {
        alert("Passwords dont match")
      } else {
        const { current_password, new_password, confirm_password } = this.passwordDTO;
        this.authService.changePassword({ current_password, new_password }).subscribe(
          () => {
            this.authService.getInfoActualUser().subscribe(data => {
              this.user = data;
              alert('Password changed successfully');
              this.cancelChangePassword();
            });
          },
          error => {
            alert('Error changing password: ' + error.error.message);
          }
        );
      }
    }
  }
}

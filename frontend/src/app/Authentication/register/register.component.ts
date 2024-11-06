import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';
import { UserRegister } from '../../DTOs/UserRegister';
import { AuthenticationService } from '../authentication.service';
import { UserService } from '../../User/user.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule
  ],
  templateUrl: './register.component.html',
  styleUrl: './register.component.css'
})
export class RegisterComponent implements OnInit {

  userRegisterDTO: UserRegister = {
    admin_username: '',
    admin_password: '',
    username: '',
    password: '',
    confirm_password: '',
    first_name: '',
    last_name: '',
    email: ''
  };

  admin_usernameError: boolean;
  admin_passwordError: boolean;
  usernameError: boolean;
  passwordError: boolean;
  confirm_passwordError: boolean;
  first_nameError: boolean;
  last_nameError: boolean;
  emailError: boolean;
  badUsernameError: boolean;
  badPasswordError: boolean;
  badConfirmPasswordError: boolean;
  badEmailError: boolean;
  
  showPassword: boolean;
  showConfirmPassword: boolean;

  usernamePattern = /^(?=.*[a-z])(?=.*\d)[A-Za-z\d]{6,}$/;
  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;
  emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;

  constructor(private autenticacionService: AuthenticationService, private userService: UserService, private router: Router) {
    this.admin_usernameError = false;
    this.admin_passwordError = false;
    this.usernameError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.first_nameError = false;
    this.last_nameError = false;
    this.emailError = false;
    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;
    this.badEmailError = false;

    this.showPassword = false;
    this.showConfirmPassword = false;
  }

  ngOnInit(): void {
    if (this.autenticacionService.valorUsuarioActual != null) {
      this.router.navigate(['/dashboard']);
    }
  }

  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.registerUser();
    }
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  toggleConfirmPasswordVisibility() {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  registerUser() {
    this.admin_usernameError = false;
    this.admin_passwordError = false;
    this.usernameError = false;
    this.passwordError = false;
    this.confirm_passwordError = false;
    this.first_nameError = false;
    this.last_nameError = false;
    this.emailError = false;
    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badConfirmPasswordError = false;
    this.badEmailError = false;

    if (this.userRegisterDTO.admin_username === '') {
      this.admin_usernameError = true;
    }

    if (this.userRegisterDTO.admin_password === '') {
      this.admin_passwordError = true;
    }
  
    if (this.userRegisterDTO.username === '') {
      this.usernameError = true; 
    } else if (!this.usernamePattern.test(this.userRegisterDTO.username)) {
      this.badUsernameError = true;
    }
  
    if (this.userRegisterDTO.password === '') {
      this.passwordError = true; 
    } else if (!this.passwordPattern.test(this.userRegisterDTO.password)) {
      this.badPasswordError = true;
    }

    if (this.userRegisterDTO.confirm_password === '') {
      this.confirm_passwordError = true; 
    } else if (!this.passwordPattern.test(this.userRegisterDTO.confirm_password)) {
      this.badConfirmPasswordError = true;
    }
  
    if (this.userRegisterDTO.first_name === '') {
      this.first_nameError = true;
    }
  
    if (this.userRegisterDTO.last_name === '') {
      this.last_nameError = true;
    }
  
    if (this.userRegisterDTO.email === '') {
      this.emailError = true; 
    } else if (!this.emailPattern.test(this.userRegisterDTO.email)) {
      this.badEmailError = true;
    }
  
    if (
      this.userRegisterDTO.admin_username !== '' &&
      this.userRegisterDTO.admin_password !== '' &&
      this.userRegisterDTO.username !== '' &&
      this.userRegisterDTO.password !== '' &&
      this.userRegisterDTO.confirm_password !== '' &&
      this.userRegisterDTO.first_name !== '' &&
      this.userRegisterDTO.last_name !== '' &&
      this.userRegisterDTO.email !== '' &&
      !this.badUsernameError &&
      !this.badPasswordError &&
      !this.badConfirmPasswordError &&
      !this.badEmailError
    ) {
      if (this.userRegisterDTO.password != this.userRegisterDTO.confirm_password) {
        alert("Passwords dont match")
      } else {
        this.userService.register(this.userRegisterDTO).subscribe(
          (data) => {
            this.router.navigate(['/login']);
          },
          (error) => {
            let errorMessage = 'An unexpected error occurred. Please try again.';
            if (error.error && error.error.error) {
              errorMessage = error.error.error;
            }
        
            alert(errorMessage);
          }
        );
      }
    }
  }
}

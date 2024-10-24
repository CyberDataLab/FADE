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
    username: '',
    password: '',
    name: '',
    lastName: '',
    email: ''
  };

  usernameError: boolean;
  passwordError: boolean;
  nameError: boolean;
  lastNameError: boolean;
  emailError: boolean;
  badUsernameError: boolean;
  badPasswordError: boolean;
  badEmailError: boolean;

  usernamePattern = /^(?=.*[a-z])(?=.*\d)[A-Za-z\d]{6,}$/;
  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;
  emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;

  constructor(
    private autenticacionService: AuthenticationService,
    private userService: UserService,
    private router: Router
  ) {
    this.usernameError = false;
    this.passwordError = false;
    this.nameError = false;
    this.lastNameError = false;
    this.emailError = false;
    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badEmailError = false;
  }

  ngOnInit(): void {
    if (this.autenticacionService.valorUsuarioActual != null) {
      this.router.navigate(['/dashboard']);
    }
  }

  registerUser() {
    this.usernameError = false;
    this.passwordError = false;
    this.nameError = false;
    this.lastNameError = false;
    this.emailError = false;
    this.badUsernameError = false;
    this.badPasswordError = false;
    this.badEmailError = false;
  
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
  
    if (this.userRegisterDTO.name === '') {
      this.nameError = true;
    }
  
    if (this.userRegisterDTO.lastName === '') {
      this.lastNameError = true;
    }
  
    if (this.userRegisterDTO.email === '') {
      this.emailError = true; 
    } else if (!this.emailPattern.test(this.userRegisterDTO.email)) {
      this.badEmailError = true;
    }
  
    if (
      this.userRegisterDTO.username !== '' &&
      this.userRegisterDTO.password !== '' &&
      this.userRegisterDTO.name !== '' &&
      this.userRegisterDTO.lastName !== '' &&
      this.userRegisterDTO.email !== '' &&
      !this.badUsernameError &&
      !this.badPasswordError &&
      !this.badEmailError
    ) {
      this.userService.register(this.userRegisterDTO).subscribe(
        (data) => {
          this.router.navigate(['/login']);
        },
        (error) => {
          alert('User already registered.');
        }
      );
    }
  }
  
}

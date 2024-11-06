import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule, ActivatedRoute, Params } from '@angular/router';
import { UserPatch } from '../../DTOs/UserPatch';
import { UserService } from '../../User/user.service';


@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterModule,
  ],
  templateUrl: './reset-password.component.html',
  styleUrl: './reset-password.component.css'
})
export class ResetPasswordComponent {
  userPatchDTO: UserPatch = {
    username: '',
    old_password: '',
    new_password: '',
    confirm_new_password: '',
    email: ''
  };
  
  showPassword: boolean;
  showConfirmPassword: boolean;

  token: string;

  new_passwordError: boolean;
  confirm_new_passwordError: boolean;
  badNew_passwordError: boolean;
  badConfirm_new_passwordError: boolean;

  passwordPattern = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[A-Za-z\d]{8,}$/;

  constructor(private route: ActivatedRoute, private userService: UserService, private router: Router) { 
    this.new_passwordError = false;
    this.confirm_new_passwordError = false;
    this.badNew_passwordError = false;
    this.badConfirm_new_passwordError = false;
    this.token = ''; 
    this.showPassword = false;
    this.showConfirmPassword = false;
  }

  ngOnInit(): void {
    this.route.queryParams.subscribe((params: Params) => {
      this.token = params['token'];
    });
  }

  keyDownFunction(event: KeyboardEvent): void{
    if (event.key === 'Enter'){
      this.resetPassword();
    }
  }

  togglePasswordVisibility() {
    this.showPassword = !this.showPassword;
  }

  toggleConfirmPasswordVisibility() {
    this.showConfirmPassword = !this.showConfirmPassword;
  }

  resetPassword() {
    this.new_passwordError = false;
    this.confirm_new_passwordError = false;
    this.badNew_passwordError = false;
    this.badConfirm_new_passwordError = false;

  
    if (this.userPatchDTO.new_password === '') {
      this.new_passwordError = true; 
    } else if (!this.passwordPattern.test(this.userPatchDTO.new_password)) {
      this.badNew_passwordError = true;
    }
  
    if (this.userPatchDTO.confirm_new_password === '') {
      this.confirm_new_passwordError = true; 
    } else if (!this.passwordPattern.test(this.userPatchDTO.confirm_new_password)) {
      this.badConfirm_new_passwordError = true;
    }
  
    if (
      this.userPatchDTO.new_password !== '' &&
      this.userPatchDTO.confirm_new_password !== '' &&
      !this.badNew_passwordError &&
      !this.badConfirm_new_passwordError
    ) {
      if (this.userPatchDTO.new_password != this.userPatchDTO.confirm_new_password) {
        alert("Passwords dont match")
      } else {
        this.userService.reset_password(this.userPatchDTO.new_password, this.token).subscribe(
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
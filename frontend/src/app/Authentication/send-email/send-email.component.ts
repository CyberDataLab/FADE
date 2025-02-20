import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { CommonModule } from '@angular/common'; 
import { FormsModule } from '@angular/forms'; 
import { RouterModule } from '@angular/router';
import { UserPatch } from '../../DTOs/UserPatch';
import { UserService } from '../../User/user.service';


@Component({
    selector: 'app-send-email',
    imports: [
        CommonModule,
        FormsModule,
        RouterModule
    ],
    templateUrl: './send-email.component.html',
    styleUrl: './send-email.component.css'
})
export class SendEmailComponent {
  userPatchDTO: UserPatch = {
    username: '',
    old_password: '',
    new_password: '',
    confirm_new_password: '',
    email: ''
  };

  emailError: boolean;
  badEmailError: boolean;
  emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}$/;

  constructor(private userService: UserService, private router: Router) { 
    this.emailError = false;
    this.badEmailError = false;
  }

  ngOnInit(): void {
  }

  sendEmail(): void {
    this.emailError = false;

    if (this.userPatchDTO.email === '') {
      this.emailError = true; 
    } else if (!this.emailPattern.test(this.userPatchDTO.email)) {
      this.badEmailError = true;
    }
  
    if (
      this.userPatchDTO.email !== '' &&
      !this.badEmailError
    ) {
      this.userService.sendEmail(this.userPatchDTO).subscribe(
        (data) => {
          this.router.navigate(['/login']);
        },
        (error) => {
          alert("The entered email address is not in the database");
        } 
      );
    }
  }







}

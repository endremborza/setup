#! /usr/bin/env nu

def main [root_path: string] {
  ls $root_path | get name | filter {|e| $e | str ends-with ".pub"} | each {
    |e| 
      let username = $e | split row "." | get 0 | split row "/" | last;
      echo $username;
      try {sudo useradd -m $username} catch {echo 'user exists'};
      sudo chsh -s /bin/bash $username;
      let dirs = [
          $"/home/($username)/.ssh",
          $"/mnt/hdd/($username)",
      ]
      $dirs | each {|d|
        sudo mkdir -p $d;
        sudo chown $"($username):($username)" $d;
      }
      let ak_p = $"/home/($username)/.ssh/authorized_keys";
      cat $e | sudo tee $ak_p;
      sudo chown $"($username):($username)" $ak_p;
  }
}

#include <stdio.h>
#include <stdlib.h>

int main() {
    int status;

    // 1. 创建目录 TEMP_DIR
    status = system("mkdir TEMP_DIR");
    if (status == -1) {
        perror("Error creating TEMP_DIR");
        return 1;
    }

    // 2. 切换到 TEMP_DIR 目录
    status = system("cd TEMP_DIR");
    if (status == -1) {
        perror("Error changing directory to TEMP_DIR");
        return 1;
    }

    // 3. 从 /etc/ 复制包含“conf”或“d”的文件到 TEMP_DIR
    status = system("cp -r /etc/*conf* /etc/*d* TEMP_DIR/");
    if (status == -1) {
        perror("Error copying files to TEMP_DIR");
        return 1;
    }

    // 4. 列出以 "s" 开头的文件并保存到 listS 文件
    status = system("ls TEMP_DIR/s* > TEMP_DIR/listS");
    if (status == -1) {
        perror("Error listing files starting with 's'");
        return 1;
    }

    // 5. 列出以 "c" 开头的文件并保存到 listC 文件
    status = system("ls TEMP_DIR/c* > TEMP_DIR/listC");
    if (status == -1) {
        perror("Error listing files starting with 'c'");
        return 1;
    }

    // 6. 合并并排序 listS 和 listC 文件到 final_list
    status = system("cat TEMP_DIR/listS TEMP_DIR/listC | sort > TEMP_DIR/final_list");
    if (status == -1) {
        perror("Error merging and sorting files");
        return 1;
    }

    // 7. 将 final_list 文件复制到父目录
    status = system("cp TEMP_DIR/final_list ..");
    if (status == -1) {
        perror("Error copying final_list to parent directory");
        return 1;
    }

    // 8. 删除 TEMP_DIR 及其所有内容
    // status = system("rm -r TEMP_DIR");
    // if (status == -1) {
    //     perror("Error removing TEMP_DIR");
    //     return 1;
    // }

    printf("All operations completed successfully.\n");
    return 0;
}

Part 1: Program Implementation 
Correctness: (4 points)
Code Quality and Comments: No problem (3 point)
Functionality and Error Handling: Please add error handling (1 point)
Part 2: Conceptual Analysis 
Behavior Analysis:  No problem(5 point)
System Call Reflection: Please provide specific improvement methods (1 point)
Optimization Exploration: No problem (2 point) 

Suggested Modifications:
1.Make an error judgment in the code as follows:
status = system("mkdir TEMP_DIR");
if (status == -1) {
perror("Error creating TEMP_DIR");
return 1;
}
